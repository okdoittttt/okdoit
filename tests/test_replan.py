"""Replan 노드 단위 테스트."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from core.nodes.replan import _compose_replan_input, replan
from core.state import AgentState


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "https://example.com",
        "screenshot_path": None,
        "dom_text": "현재 DOM 텍스트",
        "last_action": None,
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 7,
        "subtasks": [
            {"description": "기존 단계1", "done": True},
            {"description": "기존 단계2", "done": False},
        ],
        "memory": "지금까지 페이지 X에서 정보 A 수집",
        "history_items": [
            {"step": 0, "thought": "이동", "action": {"type": "navigate", "value": "https://x.com"}, "memory_update": None},
            {"step": 2, "thought": "클릭 시도", "action": {"type": "click_index", "index": 3}, "memory_update": None},
        ],
        "plan_stale": True,
        "subtask_start_iter": 2,
        "prev_active_subtask": 1,
        "replan_count": 0,
    }
    return {**base, **kwargs}


def _make_llm_mock(response_text: str) -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_text))
    mock_llm.extract_text = MagicMock(side_effect=lambda resp: resp.content)
    return mock_llm


# ── _compose_replan_input ────────────────────────────────────────────────────


def test_compose_replan_input_contains_all_blocks():
    """입력 메시지에 task/계획/메모/히스토리/URL/DOM 블록이 모두 포함된다."""
    state = make_state()
    msg = _compose_replan_input(state)
    assert "[원 목표]" in msg
    assert "테스트 태스크" in msg
    assert "[기존 계획과 진행 상태]" in msg
    assert "기존 단계1" in msg
    assert "기존 단계2" in msg
    assert "✅" in msg and "⬜" in msg
    assert "[기억 메모]" in msg
    assert "지금까지 페이지 X에서 정보 A 수집" in msg
    assert "[최근 액션]" in msg
    assert "click_index" in msg
    assert "[현재 URL]" in msg
    assert "https://example.com" in msg
    assert "[현재 DOM 일부]" in msg
    assert "현재 DOM 텍스트" in msg


def test_compose_replan_input_handles_empty_history_and_memory():
    """history와 memory가 비어 있어도 (없음) 표시로 안전하게 포맷된다."""
    state = make_state(history_items=[], memory="")
    msg = _compose_replan_input(state)
    assert "(아직 액션 없음)" in msg
    assert "(없음)" in msg


def test_compose_replan_input_truncates_long_dom():
    """DOM이 매우 길면 잘려서 포함된다."""
    state = make_state(dom_text="x" * 5000)
    msg = _compose_replan_input(state)
    assert "...(이하 생략)" in msg


# ── replan() 본체 ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replan_replaces_subtasks_and_resets_flags():
    """LLM이 새 계획을 돌려주면 subtasks가 교체되고 plan_stale이 False로 리셋된다."""
    new_plan = ["새 단계 A", "새 단계 B", "새 단계 C"]
    mock_llm = _make_llm_mock(json.dumps(new_plan))

    with patch("core.nodes.replan.build_llm", return_value=mock_llm):
        result = await replan(make_state())

    assert [s["description"] for s in result["subtasks"]] == new_plan
    assert all(s["done"] is False for s in result["subtasks"])
    assert result["plan_stale"] is False
    assert result["replan_count"] == 1
    assert result["subtask_start_iter"] == result["iterations"]
    assert result["prev_active_subtask"] == -1


@pytest.mark.asyncio
async def test_replan_keeps_existing_plan_when_parse_fails():
    """LLM이 JSON 아닌 응답을 내면 기존 subtasks를 유지하고 plan_stale만 끈다."""
    mock_llm = _make_llm_mock("응답이 JSON이 아님")
    state = make_state()
    original_subtasks = state["subtasks"]

    with patch("core.nodes.replan.build_llm", return_value=mock_llm):
        result = await replan(state)

    assert result["subtasks"] == original_subtasks
    assert result["plan_stale"] is False
    assert result["replan_count"] == 1


@pytest.mark.asyncio
async def test_replan_increments_replan_count():
    """이미 호출된 적 있으면 replan_count가 누적된다."""
    mock_llm = _make_llm_mock(json.dumps(["A", "B"]))
    with patch("core.nodes.replan.build_llm", return_value=mock_llm):
        result = await replan(make_state(replan_count=2))
    assert result["replan_count"] == 3


@pytest.mark.asyncio
async def test_replan_records_error_on_llm_failure():
    """LLM 호출 자체가 실패하면 error 필드에 기록되고 plan_stale은 꺼진다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("connection refused"))

    with patch("core.nodes.replan.build_llm", return_value=mock_llm):
        result = await replan(make_state())

    assert result["error"] is not None
    assert "[replan]" in result["error"]
    assert result["plan_stale"] is False
    assert result["replan_count"] == 1


@pytest.mark.asyncio
async def test_replan_clears_plan_stale_even_on_empty_response():
    """빈 배열 응답도 파싱 실패와 동일 처리: plan_stale만 끄고 기존 plan 유지."""
    mock_llm = _make_llm_mock("[]")
    state = make_state()
    original = state["subtasks"]
    with patch("core.nodes.replan.build_llm", return_value=mock_llm):
        result = await replan(state)
    assert result["subtasks"] == original
    assert result["plan_stale"] is False
