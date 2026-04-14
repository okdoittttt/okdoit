import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.nodes.think import _apply_step_done, _build_messages, _format_plan, _parse_response, think
from core.state import AgentState

load_dotenv()


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "https://example.com",
        "screenshot_path": None,
        "dom_text": "Example Domain",
        "last_action": None,
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 0,
        "subtasks": [],
    }
    return {**base, **kwargs}


# ── _parse_response 단위 테스트 ────────────────────────────────────────────────

def test_parse_response_valid():
    """올바른 JSON 응답을 파싱한다."""
    action = {"type": "click", "value": "로그인 버튼"}
    raw = json.dumps({
        "thought": "페이지를 확인했다",
        "action": action,
        "is_done": False,
        "result": None,
    })
    parsed = _parse_response(raw)
    assert parsed["action"] == action
    assert parsed["is_done"] is False
    assert "error" not in parsed


def test_parse_response_invalid_json():
    """JSON이 아닌 응답이면 error를 반환한다."""
    parsed = _parse_response("이건 JSON이 아닙니다.")
    assert "error" in parsed
    assert "[think]" in parsed["error"]


def test_parse_response_is_done_without_result():
    """is_done=True인데 result가 없으면 error를 반환한다."""
    raw = json.dumps({
        "thought": "완료",
        "action": {"type": "wait", "value": 0},
        "is_done": True,
        "result": None,
    })
    parsed = _parse_response(raw)
    assert "error" in parsed


def test_parse_response_is_done_with_result():
    """is_done=True이고 result가 있으면 정상 파싱한다."""
    raw = json.dumps({
        "thought": "완료",
        "action": {"type": "wait", "value": 0},
        "is_done": True,
        "result": "최종 결과입니다.",
    })
    parsed = _parse_response(raw)
    assert parsed["is_done"] is True
    assert parsed["result"] == "최종 결과입니다."
    assert "error" not in parsed


# ── _build_messages 단위 테스트 ───────────────────────────────────────────────

def test_build_messages_structure():
    """메시지 리스트가 SystemMessage → HumanMessage 순서인지 확인한다."""
    state = make_state()
    messages = _build_messages(state)

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[-1], HumanMessage)


def test_build_messages_contains_task_and_url():
    """HumanMessage에 task와 current_url이 포함되는지 확인한다."""
    state = make_state(task="구글 검색", current_url="https://google.com")
    messages = _build_messages(state)

    human = messages[-1]
    text_block = human.content[0]["text"]
    assert "구글 검색" in text_block
    assert "https://google.com" in text_block


def test_build_messages_includes_history():
    """이전 대화 히스토리가 메시지 리스트에 포함되는지 확인한다."""
    history = [AIMessage(content="이전 응답")]
    state = make_state(messages=history)
    messages = _build_messages(state)

    assert any(isinstance(m, AIMessage) for m in messages)


def test_build_messages_no_screenshot_when_path_is_none():
    """screenshot_path가 None이면 이미지 블록이 없는지 확인한다."""
    state = make_state(screenshot_path=None)
    messages = _build_messages(state)

    human = messages[-1]
    assert len(human.content) == 1
    assert human.content[0]["type"] == "text"


def test_build_messages_includes_screenshot(tmp_path):
    """screenshot_path가 있으면 이미지 블록이 포함되는지 확인한다."""
    img = tmp_path / "step_0.png"
    img.write_bytes(b"\x89PNG\r\n")

    state = make_state(screenshot_path=str(img))
    messages = _build_messages(state)

    human = messages[-1]
    assert len(human.content) == 2
    assert human.content[1]["type"] == "image_url"
    assert human.content[1]["image_url"]["url"].startswith("data:image/png;base64,")


# ── think() 단위 테스트 (LLM mock) ────────────────────────────────────────────

def _make_llm_mock(response_json: dict) -> MagicMock:
    """LLM mock을 생성한다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content=json.dumps(response_json))
    )
    return mock_llm


@pytest.mark.asyncio
async def test_think_updates_last_action():
    """LLM 응답의 action dict가 JSON 문자열로 last_action에 저장되는지 확인한다."""
    action = {"type": "click", "value": "로그인 버튼"}
    mock_llm = _make_llm_mock({
        "thought": "버튼을 클릭해야 한다",
        "action": action,
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["last_action"] == json.dumps(action, ensure_ascii=False)
    assert result["error"] is None


@pytest.mark.asyncio
async def test_think_appends_to_messages():
    """LLM 응답이 messages 히스토리에 추가되는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "진행 중",
        "action": {"type": "navigate", "value": "https://example.com"},
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert len(result["messages"]) == 1


@pytest.mark.asyncio
async def test_think_sets_is_done_and_result():
    """is_done=True일 때 result가 state에 저장되는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "목표 달성",
        "action": {"type": "wait", "value": 0},
        "is_done": True,
        "result": "작업 완료됐습니다.",
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["is_done"] is True
    assert result["result"] == "작업 완료됐습니다."


@pytest.mark.asyncio
async def test_think_records_error_on_invalid_json():
    """LLM이 JSON이 아닌 응답을 반환하면 error 필드에 기록되는지 확인한다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="이건 JSON이 아님"))

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is not None
    assert "[think]" in result["error"]


@pytest.mark.asyncio
async def test_think_records_error_on_llm_failure():
    """LLM 호출 자체가 실패하면 error 필드에 기록되는지 확인한다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("connection refused"))

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is not None
    assert "[think]" in result["error"]


# ── _format_plan 단위 테스트 ─────────────────────────────────────────────────

def test_format_plan_empty():
    """subtasks가 비어있으면 빈 문자열을 반환한다."""
    assert _format_plan([]) == ""


def test_format_plan_marks_first_incomplete_as_current():
    """첫 번째 미완료 단계에 ▶ 아이콘이 붙는지 확인한다."""
    subtasks = [
        {"description": "단계1", "done": True},
        {"description": "단계2", "done": False},
        {"description": "단계3", "done": False},
    ]
    result = _format_plan(subtasks)
    assert "✅ 1. 단계1" in result
    assert "▶ 2. 단계2  (현재)" in result
    assert "⬜ 3. 단계3" in result


def test_format_plan_all_done():
    """모든 단계가 완료되면 ✅만 표시한다."""
    subtasks = [
        {"description": "단계1", "done": True},
        {"description": "단계2", "done": True},
    ]
    result = _format_plan(subtasks)
    assert "▶" not in result
    assert "✅ 1. 단계1" in result
    assert "✅ 2. 단계2" in result


def test_format_plan_all_pending():
    """모든 단계가 미완료이면 첫 번째만 ▶이고 나머지는 ⬜이다."""
    subtasks = [
        {"description": "A", "done": False},
        {"description": "B", "done": False},
    ]
    result = _format_plan(subtasks)
    assert "▶ 1. A  (현재)" in result
    assert "⬜ 2. B" in result


# ── _apply_step_done 단위 테스트 ──────────────────────────────────────────────

def test_apply_step_done_marks_first_incomplete():
    """step_done=True이면 첫 번째 미완료 단계가 done=True로 변경된다."""
    subtasks = [
        {"description": "단계1", "done": True},
        {"description": "단계2", "done": False},
        {"description": "단계3", "done": False},
    ]
    result = _apply_step_done(subtasks, step_done=True)
    assert result[0]["done"] is True
    assert result[1]["done"] is True
    assert result[2]["done"] is False


def test_apply_step_done_false_returns_unchanged():
    """step_done=False이면 subtasks가 변경되지 않는다."""
    subtasks = [{"description": "단계1", "done": False}]
    result = _apply_step_done(subtasks, step_done=False)
    assert result[0]["done"] is False


def test_apply_step_done_does_not_mutate_original():
    """원본 subtasks가 변경되지 않는지 확인한다."""
    subtasks = [{"description": "단계1", "done": False}]
    _apply_step_done(subtasks, step_done=True)
    assert subtasks[0]["done"] is False


# ── think()에서 step_done 처리 테스트 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_think_advances_subtask_when_step_done():
    """LLM이 step_done=True를 반환하면 첫 번째 미완료 단계가 done으로 업데이트된다."""
    action = {"type": "click", "value": "확인"}
    mock_llm = _make_llm_mock({
        "thought": "이 단계 완료",
        "action": action,
        "step_done": True,
        "is_done": False,
        "result": None,
    })
    subtasks = [
        {"description": "단계1", "done": False},
        {"description": "단계2", "done": False},
    ]
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(subtasks=subtasks))

    assert result["subtasks"][0]["done"] is True
    assert result["subtasks"][1]["done"] is False


@pytest.mark.asyncio
async def test_think_does_not_advance_subtask_when_step_not_done():
    """LLM이 step_done=False를 반환하면 subtasks가 변경되지 않는다."""
    action = {"type": "click", "value": "확인"}
    mock_llm = _make_llm_mock({
        "thought": "아직 진행 중",
        "action": action,
        "step_done": False,
        "is_done": False,
        "result": None,
    })
    subtasks = [{"description": "단계1", "done": False}]
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(subtasks=subtasks))

    assert result["subtasks"][0]["done"] is False


@pytest.mark.asyncio
async def test_build_messages_includes_plan_section():
    """subtasks가 있으면 [작업 계획] 섹션이 HumanMessage에 포함되는지 확인한다."""
    subtasks = [
        {"description": "페이지 이동", "done": True},
        {"description": "버튼 클릭", "done": False},
    ]
    state = make_state(subtasks=subtasks)
    messages = _build_messages(state)

    human = messages[-1]
    text = human.content[0]["text"]
    assert "[작업 계획]" in text
    assert "✅" in text
    assert "▶" in text


# ── think() 통합 테스트 ────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_think_integration_with_ollama():
    """실제 Ollama LLM을 호출해서 think()가 정상 동작하는지 확인한다."""
    result = await think(make_state())

    assert result["last_action"] is not None
    assert result["error"] is None
    assert len(result["messages"]) == 1
