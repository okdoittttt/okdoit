import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.nodes.think import (
    KEEP_LAST_ITEMS,
    MAX_MEMORY_CHARS,
    _append_history_item,
    _apply_step_done,
    _build_messages,
    _format_history_block,
    _format_plan,
    _parse_response,
    _truncate,
    _update_memory,
    think,
)
from core.state import AgentState, HistoryItem

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
        "memory": "",
        "history_items": [],
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


def test_build_messages_does_not_replay_raw_messages():
    """state['messages']의 과거 AIMessage는 LLM 입력에 직접 포함되지 않는다.

    컴팩션 도입 이후 history_items/memory로 대체되었다. messages는 감사 로그
    용도로만 유지된다.
    """
    history = [AIMessage(content="이전 응답")]
    state = make_state(messages=history)
    messages = _build_messages(state)

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert not any(isinstance(m, AIMessage) for m in messages)


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
    """LLMAdapter mock을 생성한다."""
    content = json.dumps(response_json)
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    mock_llm.extract_text = MagicMock(return_value=content)
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
    mock_llm.extract_text = MagicMock(return_value="이건 JSON이 아님")

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


def test_build_messages_includes_error_section():
    """last_action_error가 있으면 [이전 액션 오류] 섹션이 포함되는지 확인한다."""
    state = make_state(last_action_error="[act] 클릭할 요소를 찾을 수 없습니다: '버튼'")
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert "[이전 액션 오류]" in text
    assert "[act] 클릭할 요소를 찾을 수 없습니다: '버튼'" in text
    assert "다른 방법으로 동일한 목표를 달성하세요" in text


def test_build_messages_no_error_section_when_none():
    """last_action_error가 None이면 [이전 액션 오류] 섹션이 없는지 확인한다."""
    state = make_state(last_action_error=None)
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert "[이전 액션 오류]" not in text


@pytest.mark.asyncio
async def test_think_clears_last_action_error():
    """think 성공 시 last_action_error가 None으로 클리어되는지 확인한다."""
    mock_llm = _make_llm_mock({
        "thought": "다른 방법 시도",
        "action": {"type": "navigate", "value": "https://example.com"},
        "step_done": False,
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(last_action_error="[act] 클릭 실패"))

    assert result["last_action_error"] is None


# ── Gemini 리스트 응답 처리 테스트 ───────────────────────────────────────────────

def _make_gemini_llm_mock(content) -> MagicMock:
    """Gemini 스타일 응답(content가 리스트)을 반환하는 LLMAdapter mock을 생성한다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    extracted = (
        next(
            (b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"),
            str(content),
        )
        if isinstance(content, list)
        else content
    )
    mock_llm.extract_text = MagicMock(return_value=extracted)
    return mock_llm


@pytest.mark.asyncio
async def test_think_handles_gemini_thinking_plus_text_list():
    """Gemini 2.5 Pro처럼 content가 [thinking 블록, text 블록] 리스트일 때 text 블록을 추출해 파싱한다."""
    action = {"type": "navigate", "value": "https://finance.naver.com"}
    response_json = json.dumps({
        "thought": "네이버 금융으로 이동한다",
        "action": action,
        "is_done": False,
        "result": None,
    })
    content = [
        {"type": "thinking", "thinking": "사용자가 네이버 금융으로 이동하길 원한다..."},
        {"type": "text", "text": response_json},
    ]
    mock_llm = _make_gemini_llm_mock(content)

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is None
    assert result["last_action"] == json.dumps(action, ensure_ascii=False)


@pytest.mark.asyncio
async def test_think_handles_gemini_text_only_list():
    """content가 [text 블록] 단독 리스트일 때도 정상 파싱한다."""
    action = {"type": "click", "value": "삼성전자"}
    response_json = json.dumps({
        "thought": "삼성전자를 클릭한다",
        "action": action,
        "is_done": False,
        "result": None,
    })
    content = [{"type": "text", "text": response_json}]
    mock_llm = _make_gemini_llm_mock(content)

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is None
    assert result["last_action"] == json.dumps(action, ensure_ascii=False)


@pytest.mark.asyncio
async def test_think_handles_gemini_list_with_no_text_block():
    """content 리스트에 text 블록이 없으면 error를 기록하고 반환한다."""
    content = [{"type": "thinking", "thinking": "생각만 있고 응답 없음"}]
    mock_llm = _make_gemini_llm_mock(content)

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is not None
    assert "[think]" in result["error"]


@pytest.mark.asyncio
async def test_think_handles_gemini_list_with_is_done():
    """content가 리스트일 때 is_done=True와 result도 정상 처리된다."""
    response_json = json.dumps({
        "thought": "목표 달성",
        "action": {"type": "wait", "value": 0},
        "is_done": True,
        "result": "게시글 5개 제목입니다.",
    })
    content = [
        {"type": "thinking", "thinking": "작업이 완료됐다"},
        {"type": "text", "text": response_json},
    ]
    mock_llm = _make_gemini_llm_mock(content)

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is None
    assert result["is_done"] is True
    assert result["result"] == "게시글 5개 제목입니다."


@pytest.mark.asyncio
async def test_think_handles_gemini_list_with_code_fence():
    """Gemini가 text 블록 안에 코드 펜스를 포함해도 정상 파싱한다."""
    action = {"type": "scroll", "value": "down"}
    response_json = f"```json\n{json.dumps({'thought': '스크롤', 'action': action, 'is_done': False, 'result': None})}\n```"
    content = [
        {"type": "thinking", "thinking": "스크롤이 필요하다"},
        {"type": "text", "text": response_json},
    ]
    mock_llm = _make_gemini_llm_mock(content)

    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result["error"] is None
    assert result["last_action"] == json.dumps(action, ensure_ascii=False)


# ── 메시지 컴팩션 / memory / history_items 테스트 ─────────────────────────────

def _make_history(n: int, start: int = 0) -> list[HistoryItem]:
    """n개의 더미 HistoryItem을 만든다. step은 start부터 순차 증가."""
    return [
        {
            "step": start + i,
            "thought": f"스텝 {start + i} 분석",
            "action": {"type": "click", "value": f"버튼{start + i}"},
            "memory_update": None,
        }
        for i in range(n)
    ]


def test_build_messages_returns_exactly_two_messages():
    """LLM 입력은 항상 [System, Human] 2개로 고정된다."""
    state = make_state(
        messages=[AIMessage(content="옛 응답1"), AIMessage(content="옛 응답2")],
        history_items=_make_history(3),
        memory="누적 요약",
    )
    messages = _build_messages(state)

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)


def test_build_messages_includes_memory_block():
    """memory가 있으면 [기억 메모] 섹션이 포함된다."""
    state = make_state(memory="지금까지 A, B를 수집했다. 다음은 C.")
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert "[기억 메모]" in text
    assert "지금까지 A, B를 수집했다" in text


def test_build_messages_omits_memory_block_when_empty():
    """memory가 비어있으면 [기억 메모] 섹션 자체가 없다."""
    state = make_state(memory="")
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert "[기억 메모]" not in text


def test_build_messages_includes_recent_history_items():
    """history_items가 있으면 [최근 액션] 섹션에 step/thought/action이 표시된다."""
    history = _make_history(3)
    state = make_state(history_items=history)
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert "[최근 액션]" in text
    for item in history:
        assert f"#{item['step']}" in text
        assert item["thought"] in text
    assert "click" in text


def test_build_messages_omits_old_history_items_beyond_keep_last():
    """history_items가 KEEP_LAST_ITEMS보다 많으면 오래된 것은 생략 헤더로 대체된다."""
    total = KEEP_LAST_ITEMS + 3
    history = _make_history(total)
    state = make_state(history_items=history)
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert f"앞선 3개 스텝 생략" in text
    # 최근 KEEP_LAST_ITEMS개만 thought가 원본으로 실린다
    for item in history[-KEEP_LAST_ITEMS:]:
        assert item["thought"] in text
    # 생략된 항목의 thought는 원본으로 실리지 않는다
    for item in history[:-KEEP_LAST_ITEMS]:
        assert item["thought"] not in text


def test_build_messages_omits_history_section_when_empty():
    """history_items가 비어있으면 [최근 액션] 섹션 자체가 없다."""
    state = make_state(history_items=[])
    messages = _build_messages(state)

    text = messages[-1].content[0]["text"]
    assert "[최근 액션]" not in text


def test_build_messages_includes_only_current_screenshot(tmp_path):
    """스크린샷은 현재 턴 파일 하나만 image_url 블록으로 포함된다.

    과거 스크린샷이 messages/history에 참조되어 있어도 LLM 입력에는 들어가지 않는다.
    """
    img = tmp_path / "step_5.png"
    img.write_bytes(b"\x89PNG\r\n")
    state = make_state(
        screenshot_path=str(img),
        history_items=_make_history(3),
        messages=[AIMessage(content="옛 응답")],
    )
    messages = _build_messages(state)

    human = messages[-1]
    image_blocks = [b for b in human.content if b.get("type") == "image_url"]
    assert len(image_blocks) == 1


# ── _truncate / _update_memory / _append_history_item 단위 테스트 ─────────────

def test_truncate_below_limit_returns_original():
    assert _truncate("짧은 문자열", 100) == "짧은 문자열"


def test_truncate_exceeds_limit_adds_ellipsis():
    result = _truncate("a" * 50, 10)
    assert len(result) == 10
    assert result.endswith("…")


def test_truncate_zero_limit_returns_empty():
    assert _truncate("anything", 0) == ""


def test_update_memory_none_keeps_previous():
    assert _update_memory("기존 메모", None) == "기존 메모"


def test_update_memory_empty_string_keeps_previous():
    assert _update_memory("기존 메모", "   ") == "기존 메모"


def test_update_memory_new_value_overwrites():
    assert _update_memory("기존", "새 요약") == "새 요약"


def test_update_memory_truncates_oversized():
    huge = "x" * (MAX_MEMORY_CHARS + 100)
    result = _update_memory("", huge)
    assert len(result) == MAX_MEMORY_CHARS


def test_append_history_item_does_not_mutate_original():
    """원본 history_items는 변경되지 않는다."""
    state = make_state(iterations=3, history_items=[])
    parsed = {"thought": "t", "action": {"type": "click", "value": "x"}, "memory_update": None}
    new_list = _append_history_item(state, parsed)

    assert new_list is not state["history_items"]
    assert len(state["history_items"]) == 0
    assert len(new_list) == 1
    assert new_list[0]["step"] == 3
    assert new_list[0]["action"] == {"type": "click", "value": "x"}


def test_append_history_item_coerces_non_dict_action_to_empty():
    """action이 dict가 아니면 빈 dict로 저장한다(방어적)."""
    state = make_state(iterations=1, history_items=[])
    parsed = {"thought": "t", "action": None, "memory_update": "mem"}
    new_list = _append_history_item(state, parsed)

    assert new_list[0]["action"] == {}
    assert new_list[0]["memory_update"] == "mem"


def test_format_history_block_empty_returns_empty_string():
    assert _format_history_block([]) == ""


# ── think()에서 memory/history_items 통합 동작 테스트 ─────────────────────────

@pytest.mark.asyncio
async def test_think_appends_history_item():
    """LLM 응답 후 history_items에 새 항목이 append된다."""
    action = {"type": "navigate", "value": "https://example.com"}
    mock_llm = _make_llm_mock({
        "thought": "페이지 이동",
        "action": action,
        "memory_update": "구글 이동 직전. 다음은 검색어 입력.",
        "is_done": False,
        "result": None,
    })
    initial_history = _make_history(2, start=0)
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(iterations=2, history_items=initial_history))

    assert len(result["history_items"]) == 3
    last = result["history_items"][-1]
    assert last["step"] == 2
    assert last["action"] == action
    assert last["memory_update"] == "구글 이동 직전. 다음은 검색어 입력."


@pytest.mark.asyncio
async def test_think_updates_memory_when_memory_update_present():
    """LLM이 memory_update를 내면 state['memory']가 해당 값으로 갱신된다."""
    mock_llm = _make_llm_mock({
        "thought": "진행",
        "action": {"type": "wait", "value": 1},
        "memory_update": "새 요약: 페이지 A 도달",
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(memory="이전 요약"))

    assert result["memory"] == "새 요약: 페이지 A 도달"


@pytest.mark.asyncio
async def test_think_preserves_memory_when_memory_update_absent():
    """memory_update 필드가 없으면 기존 memory를 유지한다."""
    mock_llm = _make_llm_mock({
        "thought": "진행",
        "action": {"type": "wait", "value": 1},
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(memory="유지되어야 하는 요약"))

    assert result["memory"] == "유지되어야 하는 요약"


@pytest.mark.asyncio
async def test_think_preserves_memory_when_memory_update_is_null():
    """memory_update=null이어도 기존 memory를 유지한다."""
    mock_llm = _make_llm_mock({
        "thought": "진행",
        "action": {"type": "wait", "value": 1},
        "memory_update": None,
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(memory="유지되어야 함"))

    assert result["memory"] == "유지되어야 함"


# ── plan_stale 파싱 테스트 ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_think_propagates_plan_stale_true():
    """LLM이 plan_stale=true를 응답하면 state로 전파된다."""
    mock_llm = _make_llm_mock({
        "thought": "현재 계획이 부적절",
        "action": {"type": "wait", "value": 1},
        "plan_stale": True,
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state())

    assert result.get("plan_stale") is True


@pytest.mark.asyncio
async def test_think_does_not_overwrite_existing_plan_stale_true():
    """plan_stale 필드를 응답에 안 넣어도 기존 True가 유지된다(verify 신호 보존)."""
    mock_llm = _make_llm_mock({
        "thought": "정상 진행",
        "action": {"type": "wait", "value": 1},
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(plan_stale=True))

    assert result.get("plan_stale") is True


@pytest.mark.asyncio
async def test_think_plan_stale_default_false():
    """기본 응답에는 plan_stale 키가 없거나 False여야 한다(verify의 patch가 그 위에 덮어쓰기 가능)."""
    mock_llm = _make_llm_mock({
        "thought": "정상 진행",
        "action": {"type": "wait", "value": 1},
        "is_done": False,
        "result": None,
    })
    with patch("core.nodes.think.build_llm", return_value=mock_llm):
        result = await think(make_state(plan_stale=False))

    assert result.get("plan_stale", False) is False


# ── think() 통합 테스트 ────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_think_integration_with_ollama():
    """실제 Ollama LLM을 호출해서 think()가 정상 동작하는지 확인한다."""
    result = await think(make_state())

    assert result["last_action"] is not None
    assert result["error"] is None
    assert len(result["messages"]) == 1
