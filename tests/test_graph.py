import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.graph import END

from core.graph import _should_continue, create_graph, initial_state
from core.nodes.verify import MAX_LOOP_ITERATIONS
from core.state import AgentState

load_dotenv()


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "https://example.com",
        "screenshot_path": None,
        "dom_text": None,
        "last_action": None,
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 0,
    }
    return {**base, **kwargs}


# ── initial_state 단위 테스트 ─────────────────────────────────────────────────

def test_initial_state_sets_task():
    """task가 올바르게 설정되는지 확인한다."""
    state = initial_state("구글에서 날씨 검색")
    assert state["task"] == "구글에서 날씨 검색"


def test_initial_state_defaults():
    """모든 필드가 올바른 초기값으로 설정되는지 확인한다."""
    state = initial_state("테스트")
    assert state["messages"] == []
    assert state["current_url"] == ""
    assert state["screenshot_path"] is None
    assert state["dom_text"] is None
    assert state["last_action"] is None
    assert state["is_done"] is False
    assert state["result"] is None
    assert state["error"] is None
    assert state["iterations"] == 0


# ── _should_continue 단위 테스트 ─────────────────────────────────────────────

def test_should_continue_returns_observe_when_not_done():
    """종료 조건이 없으면 observe를 반환한다."""
    assert _should_continue(make_state()) == "observe"


def test_should_continue_returns_end_when_is_done():
    """is_done=True면 END를 반환한다."""
    assert _should_continue(make_state(is_done=True)) == END


def test_should_continue_returns_observe_when_only_error():
    """error만 있고 is_done=False이면 observe를 반환한다 (verify가 종료 판단을 전담)."""
    assert _should_continue(make_state(error="[act] 오류")) == "observe"


def test_should_continue_returns_end_when_is_done_with_error():
    """is_done=True이고 error가 있어도 END를 반환한다."""
    assert _should_continue(make_state(is_done=True, error="오류")) == END


# ── create_graph 단위 테스트 ──────────────────────────────────────────────────

def test_create_graph_returns_compiled_graph():
    """create_graph()가 invoke 가능한 그래프를 반환하는지 확인한다."""
    graph = create_graph()
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


def test_create_graph_has_all_nodes():
    """그래프에 5개 노드가 모두 등록되어 있는지 확인한다."""
    graph = create_graph()
    assert "plan" in graph.nodes
    assert "observe" in graph.nodes
    assert "think" in graph.nodes
    assert "act" in graph.nodes
    assert "verify" in graph.nodes


# ── 통합 테스트 (LLM mock) ────────────────────────────────────────────────────

def _make_llm_mock(response_json: dict) -> MagicMock:
    mock_llm = MagicMock()
    response_content = json.dumps(response_json)
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_content))
    mock_llm.extract_text = MagicMock(side_effect=lambda resp: resp.content)
    return mock_llm


@pytest.mark.asyncio
async def test_graph_runs_and_terminates_on_is_done(tmp_path):
    """LLM이 첫 턴에 is_done=True를 반환하면 한 번만 실행하고 종료하는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "목표 달성",
        "action": {"type": "wait", "value": 0},
        "is_done": True,
        "result": "완료됐습니다.",
    })
    mock_page = AsyncMock()
    mock_page.url = "https://example.com"
    mock_page.evaluate = AsyncMock(return_value=[])
    mock_page.screenshot = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    mock_page.title = AsyncMock(return_value="Test Page")

    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)
    mock_manager.take_screenshot = AsyncMock(return_value=str(tmp_path / "step_0.png"))

    with (
        patch("core.nodes.observe.BrowserManager", return_value=mock_manager),
        patch("core.nodes.act.BrowserManager", return_value=mock_manager),
        patch("core.nodes.think.build_llm", return_value=mock_llm),
    ):
        graph = create_graph()
        result = await graph.ainvoke(initial_state("테스트"))

    assert result["is_done"] is True
    assert result["result"] == "완료됐습니다."
    assert result["error"] is None


@pytest.mark.asyncio
async def test_graph_terminates_after_max_consecutive_errors(tmp_path):
    """observe에서 에러가 MAX_CONSECUTIVE_ERRORS 이상 연속 발생하면 루프가 종료되는지 확인한다."""
    from core.nodes.verify import MAX_CONSECUTIVE_ERRORS

    mock_llm = _make_llm_mock({
        "thought": "에러 복구 시도",
        "action": {"type": "navigate", "value": "https://example.com"},
        "is_done": False,
        "result": None,
    })
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(side_effect=RuntimeError("browser not started"))

    with (
        patch("core.nodes.observe.BrowserManager", return_value=mock_manager),
        patch("core.nodes.act.BrowserManager", return_value=mock_manager),
        patch("core.nodes.plan.build_llm", return_value=mock_llm),
        patch("core.nodes.think.build_llm", return_value=mock_llm),
    ):
        graph = create_graph()
        result = await graph.ainvoke(initial_state("테스트"))

    assert result["is_done"] is True
    assert result["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS


@pytest.mark.asyncio
async def test_graph_terminates_on_max_iterations(tmp_path):
    """MAX_LOOP_ITERATIONS를 초과하면 루프가 종료되는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "계속 진행",
        "action": {"type": "navigate", "value": "https://example.com"},
        "is_done": False,
        "result": None,
    })
    mock_page = AsyncMock()
    mock_page.url = "https://example.com"
    mock_page.evaluate = AsyncMock(return_value=[])
    mock_page.screenshot = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    mock_page.title = AsyncMock(return_value="Test Page")

    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)
    mock_manager.take_screenshot = AsyncMock(return_value=str(tmp_path / "step.png"))

    with (
        patch("core.nodes.observe.BrowserManager", return_value=mock_manager),
        patch("core.nodes.act.BrowserManager", return_value=mock_manager),
        patch("core.nodes.think.build_llm", return_value=mock_llm),
    ):
        graph = create_graph()
        result = await graph.ainvoke(initial_state("테스트"))

    assert result["is_done"] is True
    assert result["iterations"] > MAX_LOOP_ITERATIONS
    assert result["result"] == "최대 반복 횟수를 초과했습니다."
