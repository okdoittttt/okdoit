import sys
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from agent import _print_step, _run
from core.browser import BrowserManager
from core.state import AgentState


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "https://example.com",
        "screenshot_path": None,
        "dom_text": "Example Domain",
        "last_action": "https://example.com으로 이동",
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 1,
    }
    return {**base, **kwargs}


# ── _print_step 단위 테스트 ───────────────────────────────────────────────────

def test_print_step_think_outputs_thought_and_action(capsys):
    """think 노드 출력 시 [Thought]와 [Action]이 출력되는지 확인한다.

    thought는 history_items[-1]["thought"]에서 읽는다 (단일 진실원).
    """
    state = make_state(
        history_items=[{
            "step": 1,
            "thought": "로그인이 필요하다",
            "action": {"type": "click", "value": "로그인"},
            "memory_update": None,
        }],
        last_action="로그인 버튼 클릭",
    )

    _print_step("think", state)

    captured = capsys.readouterr().out
    assert "[Thought]" in captured
    assert "로그인이 필요하다" in captured
    assert "[Action]" in captured
    assert "로그인 버튼 클릭" in captured


def test_print_step_observe_outputs_dom_text(capsys):
    """observe 노드 출력 시 [Observation]과 dom_text가 출력되는지 확인한다."""
    state = make_state(dom_text="Example Domain\n링크 텍스트")

    _print_step("observe", state)

    captured = capsys.readouterr().out
    assert "[Observation]" in captured
    assert "Example Domain" in captured


def test_print_step_observe_truncates_long_dom(capsys):
    """observe 노드 출력 시 dom_text가 100자로 잘리는지 확인한다."""
    state = make_state(dom_text="A" * 200)

    _print_step("observe", state)

    captured = capsys.readouterr().out
    assert "A" * 100 in captured
    assert "A" * 101 not in captured


def test_print_step_verify_outputs_iterations(capsys):
    """verify 노드 출력 시 [Verify]와 반복 횟수가 출력되는지 확인한다."""
    state = make_state(iterations=3)

    _print_step("verify", state)

    captured = capsys.readouterr().out
    assert "[Verify]" in captured
    assert "3" in captured


def test_print_step_act_outputs_nothing(capsys):
    """act 노드는 출력이 없는지 확인한다."""
    _print_step("act", make_state())

    captured = capsys.readouterr().out
    assert captured == ""


# ── _run 단위 테스트 (graph mock) ─────────────────────────────────────────────

def _make_graph_mock(steps: list[dict]) -> MagicMock:
    """astream()이 steps를 순서대로 반환하는 그래프 mock을 생성한다."""
    async def fake_astream(state, **kwargs):
        for step in steps:
            yield step

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream
    return mock_graph


@pytest.mark.asyncio
async def test_run_prints_success_on_completion(capsys):
    """정상 종료 시 [Success]가 출력되는지 확인한다."""
    final_state = make_state(is_done=True, result="작업 완료됐습니다.", error=None)
    mock_graph = _make_graph_mock([{"verify": final_state}])

    mock_manager = MagicMock()
    mock_manager.start = AsyncMock()
    mock_manager.stop = AsyncMock()

    with (
        patch("agent.create_graph", return_value=mock_graph),
        patch("agent.BrowserManager", return_value=mock_manager),
    ):
        await _run("테스트", mock_manager)

    captured = capsys.readouterr().out
    assert "[Success]" in captured
    assert "작업 완료됐습니다." in captured


@pytest.mark.asyncio
async def test_run_prints_error_on_failure(capsys):
    """에러 종료 시 [Error]가 출력되는지 확인한다."""
    final_state = make_state(is_done=True, error="[act] Timeout", result=None)
    mock_graph = _make_graph_mock([{"verify": final_state}])

    mock_manager = MagicMock()
    mock_manager.start = AsyncMock()
    mock_manager.stop = AsyncMock()

    with patch("agent.create_graph", return_value=mock_graph):
        await _run("테스트", mock_manager)

    captured = capsys.readouterr().out
    assert "[Error]" in captured
    assert "[act] Timeout" in captured


@pytest.mark.asyncio
async def test_run_calls_stop_even_on_exception(capsys):
    """그래프 실행 중 예외가 발생해도 stop()이 호출되는지 확인한다."""
    mock_graph = MagicMock()
    mock_graph.astream = MagicMock(side_effect=RuntimeError("graph error"))

    mock_manager = MagicMock()
    mock_manager.start = AsyncMock()
    mock_manager.stop = AsyncMock()

    with (
        patch("agent.create_graph", return_value=mock_graph),
        pytest.raises(RuntimeError),
    ):
        await _run("테스트", mock_manager)

    mock_manager.stop.assert_called_once()


# ── main() CLI 파싱 단위 테스트 ───────────────────────────────────────────────

def test_main_requires_task():
    """--task 없이 실행하면 SystemExit이 발생하는지 확인한다."""
    with patch("sys.argv", ["agent.py"]):
        with pytest.raises(SystemExit):
            from agent import main
            main()


def test_main_headless_default():
    """--no-headless 없이 실행하면 headless=True로 BrowserManager가 생성되는지 확인한다."""
    created_managers = []

    class CaptureBrowserManager:
        def __init__(self, headless=True, **kwargs):
            created_managers.append(headless)

        def __new__(cls, *args, **kwargs):
            return object.__new__(cls)

    with (
        patch("sys.argv", ["agent.py", "--task", "테스트"]),
        patch("agent.BrowserManager", CaptureBrowserManager),
        patch("agent.asyncio.run", side_effect=lambda coro: coro.close()),
        patch("agent.load_dotenv"),
    ):
        from agent import main
        main()

    assert created_managers[0] is True


def test_main_no_headless_flag():
    """--no-headless 플래그가 있으면 headless=False로 BrowserManager가 생성되는지 확인한다."""
    created_managers = []

    class CaptureBrowserManager:
        def __init__(self, headless=True, **kwargs):
            created_managers.append(headless)

        def __new__(cls, *args, **kwargs):
            return object.__new__(cls)

    with (
        patch("sys.argv", ["agent.py", "--task", "테스트", "--no-headless"]),
        patch("agent.BrowserManager", CaptureBrowserManager),
        patch("agent.asyncio.run", side_effect=lambda coro: coro.close()),
        patch("agent.load_dotenv"),
    ):
        from agent import main
        main()

    assert created_managers[0] is False
