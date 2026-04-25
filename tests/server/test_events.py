"""``server.internal.events`` 직렬화 / 역직렬화 단위 테스트."""

from __future__ import annotations

import json

import pytest

from server.internal.events import (
    PlanCreated,
    SessionFinished,
    SessionStarted,
    ServerEventEnvelope,
    StepActed,
    StepThinking,
)


def test_session_started_serializes_with_type_and_ts() -> None:
    """``type`` 리터럴과 ``ts`` 가 항상 포함되어야 한다."""
    evt = SessionStarted(session_id="abc", task="hello")
    payload = json.loads(evt.model_dump_json())
    assert payload["type"] == "session.started"
    assert payload["session_id"] == "abc"
    assert payload["task"] == "hello"
    assert "ts" in payload and isinstance(payload["ts"], str)


def test_session_finished_default_iterations_zero() -> None:
    """``iterations`` 미지정 시 0 으로 직렬화된다."""
    evt = SessionFinished(session_id="s1", result="done")
    assert evt.iterations == 0
    assert evt.result == "done"


def test_step_acted_optional_fields_round_trip() -> None:
    """실패 케이스의 모든 옵셔널 필드가 보존되어야 한다."""
    evt = StepActed(
        session_id="s1",
        iteration=3,
        action="click(index=12)",
        success=False,
        error_code="element_not_found",
        error_message="요소 없음",
        extracted=None,
    )
    payload = evt.model_dump()
    assert payload["success"] is False
    assert payload["error_code"] == "element_not_found"
    assert payload["error_message"] == "요소 없음"


def test_envelope_discriminates_by_type() -> None:
    """``ServerEventEnvelope`` 가 ``type`` 으로 정확히 분기해야 한다."""
    raw = {
        "event": {
            "session_id": "s1",
            "ts": "2026-04-25T00:00:00+00:00",
            "type": "step.thinking",
            "iteration": 1,
            "thought": "검색창에 입력",
            "action": {"name": "type", "value": "weather"},
            "memory_update": None,
        }
    }
    env = ServerEventEnvelope.model_validate(raw)
    assert isinstance(env.event, StepThinking)
    assert env.event.action == {"name": "type", "value": "weather"}


def test_plan_created_subtasks_are_passthrough() -> None:
    """``subtasks`` 는 dict 리스트 그대로 보존되어야 한다."""
    subtasks = [
        {"index": 0, "description": "검색창 입력", "done": False},
        {"index": 1, "description": "결과 클릭", "done": False},
    ]
    evt = PlanCreated(session_id="s1", subtasks=subtasks)
    assert evt.subtasks == subtasks


def test_envelope_rejects_unknown_type() -> None:
    """모르는 ``type`` 은 검증 실패해야 한다."""
    with pytest.raises(Exception):
        ServerEventEnvelope.model_validate(
            {"event": {"session_id": "s1", "type": "unknown.event"}}
        )
