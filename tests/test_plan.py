"""Plan 노드 단위 테스트."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from core.nodes.plan import _parse_subtasks, plan
from core.state import AgentState


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "구글에서 파이썬 검색 후 첫 번째 결과 클릭",
        "messages": [],
        "current_url": "",
        "screenshot_path": None,
        "dom_text": None,
        "last_action": None,
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 0,
        "subtasks": [],
    }
    return {**base, **kwargs}


# ── _parse_subtasks 단위 테스트 ───────────────────────────────────────────────

def test_parse_subtasks_valid_array():
    """올바른 JSON 배열을 파싱해서 subtask 목록을 반환한다."""
    raw = json.dumps(["구글 이동", "검색어 입력", "결과 클릭"])
    result = _parse_subtasks(raw)
    assert len(result) == 3
    assert result[0] == {"description": "구글 이동", "done": False}
    assert result[2] == {"description": "결과 클릭", "done": False}


def test_parse_subtasks_invalid_json():
    """JSON이 아닌 응답이면 빈 리스트를 반환한다."""
    result = _parse_subtasks("이건 JSON이 아닙니다")
    assert result == []


def test_parse_subtasks_not_a_list():
    """JSON 객체(배열이 아님)이면 빈 리스트를 반환한다."""
    result = _parse_subtasks(json.dumps({"steps": ["a", "b"]}))
    assert result == []


def test_parse_subtasks_filters_empty_strings():
    """빈 문자열 항목은 필터링된다."""
    raw = json.dumps(["단계1", "", "단계3"])
    result = _parse_subtasks(raw)
    assert len(result) == 2
    assert result[0]["description"] == "단계1"
    assert result[1]["description"] == "단계3"


# ── plan() 단위 테스트 (LLM mock) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_stores_subtasks_in_state():
    """LLM 응답으로 subtasks가 state에 저장되는지 확인한다."""
    steps = ["구글 이동", "검색어 입력", "결과 클릭"]
    content = json.dumps(steps)
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    mock_llm.extract_text = MagicMock(return_value=content)

    with patch("core.nodes.plan.build_llm", return_value=mock_llm):
        result = await plan(make_state())

    assert len(result["subtasks"]) == 3
    assert result["subtasks"][0]["description"] == "구글 이동"
    assert result["subtasks"][0]["done"] is False


@pytest.mark.asyncio
async def test_plan_returns_empty_subtasks_on_parse_failure():
    """LLM이 파싱 불가능한 응답을 반환하면 subtasks가 빈 리스트가 된다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="파싱 불가 응답"))
    mock_llm.extract_text = MagicMock(return_value="파싱 불가 응답")

    with patch("core.nodes.plan.build_llm", return_value=mock_llm):
        result = await plan(make_state())

    assert result["subtasks"] == []


@pytest.mark.asyncio
async def test_plan_returns_empty_subtasks_on_llm_failure():
    """LLM 호출이 실패하면 subtasks가 빈 리스트이고 error가 기록된다."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("connection refused"))

    with patch("core.nodes.plan.build_llm", return_value=mock_llm):
        result = await plan(make_state())

    assert result["subtasks"] == []
    assert result["error"] is not None
    assert "[plan]" in result["error"]


@pytest.mark.asyncio
async def test_plan_preserves_existing_state_fields():
    """plan 노드가 task, messages 등 기존 필드를 유지하는지 확인한다."""
    steps = ["단계1"]
    content = json.dumps(steps)
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    mock_llm.extract_text = MagicMock(return_value=content)

    with patch("core.nodes.plan.build_llm", return_value=mock_llm):
        result = await plan(make_state(task="원래 목표", current_url="https://example.com"))

    assert result["task"] == "원래 목표"
    assert result["current_url"] == "https://example.com"
