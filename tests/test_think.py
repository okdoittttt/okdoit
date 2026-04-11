import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.nodes.think import _build_messages, _parse_response, think
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
    }
    return {**base, **kwargs}


# ── _parse_response 단위 테스트 ────────────────────────────────────────────────

def test_parse_response_valid():
    """올바른 JSON 응답을 파싱한다."""
    raw = json.dumps({
        "thought": "페이지를 확인했다",
        "action": "로그인 버튼 클릭",
        "is_done": False,
        "result": None,
    })
    parsed = _parse_response(raw)
    assert parsed["action"] == "로그인 버튼 클릭"
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
        "action": "없음",
        "is_done": True,
        "result": None,
    })
    parsed = _parse_response(raw)
    assert "error" in parsed


def test_parse_response_is_done_with_result():
    """is_done=True이고 result가 있으면 정상 파싱한다."""
    raw = json.dumps({
        "thought": "완료",
        "action": "없음",
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
    """LLM 응답의 action이 last_action에 저장되는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "버튼을 클릭해야 한다",
        "action": "로그인 버튼 클릭",
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["last_action"] == "로그인 버튼 클릭"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_think_appends_to_messages():
    """LLM 응답이 messages 히스토리에 추가되는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "진행 중",
        "action": "다음 페이지 이동",
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
        "action": "없음",
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


# ── think() 통합 테스트 ────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_think_integration_with_ollama():
    """실제 Ollama LLM을 호출해서 think()가 정상 동작하는지 확인한다."""
    result = await think(make_state())

    assert result["last_action"] is not None
    assert result["error"] is None
    assert len(result["messages"]) == 1
