"""``server.internal.event_builders`` 순수 함수 단위 테스트.

빌더는 부수효과가 없어 dict 입력 → 이벤트 출력만 검증하면 된다.
runner 통합 테스트와 분리되어 있어 빠르게 돌고, 회귀 시 원인을 좁히기 쉽다.
"""

from __future__ import annotations

from typing import Any

from server.internal.event_builders import (
    build_plan_created,
    build_plan_replanned,
    build_step_acted,
    build_step_observed,
    build_step_thinking,
    build_step_verified,
    build_subtask_activated,
    find_active_subtask_index,
    infer_replan_reason,
    normalize_subtasks,
)


def _state(**overrides: Any) -> dict[str, Any]:
    """노드 결과 state 모방용 최소 dict."""
    base: dict[str, Any] = {
        "iterations": 0,
        "is_done": False,
        "consecutive_errors": 0,
        "current_url": "",
        "screenshot_path": None,
        "selector_map": {},
        "history_items": [],
        "last_action": None,
        "last_action_result": None,
        "subtasks": [],
        "replan_count": 0,
        "plan_stale": False,
    }
    base.update(overrides)
    return base


# ── 헬퍼 ────────────────────────────────────────────────────────


def test_normalize_subtasks_adds_index() -> None:
    """``index`` 필드가 없는 입력에 0-based index 를 부여한다."""
    out = normalize_subtasks(
        [{"description": "a", "done": True}, {"description": "b"}]
    )
    assert out == [
        {"index": 0, "description": "a", "done": True},
        {"index": 1, "description": "b", "done": False},
    ]


def test_find_active_subtask_index_returns_first_undone() -> None:
    """첫 번째 not-done 인덱스를 반환한다. 모두 완료면 -1."""
    assert find_active_subtask_index([]) == -1
    assert find_active_subtask_index([{"done": True}, {"done": True}]) == -1
    assert find_active_subtask_index([{"done": True}, {"done": False}]) == 1


def test_infer_replan_reason_branches_on_plan_stale() -> None:
    """``plan_stale=True`` 면 정체 사유, 아니면 추가 단계 사유."""
    assert "정체" in infer_replan_reason(_state(plan_stale=True))
    assert "추가" in infer_replan_reason(_state(plan_stale=False))


# ── 빌더 ────────────────────────────────────────────────────────


def test_build_plan_created_normalizes_subtasks() -> None:
    """plan 노드 state 의 subtasks 가 index 부여된 형태로 들어가야 한다."""
    state = _state(subtasks=[{"description": "a", "done": False}])
    evt = build_plan_created("s1", state)
    assert evt.session_id == "s1"
    assert evt.subtasks == [{"index": 0, "description": "a", "done": False}]


def test_build_plan_replanned_includes_reason_and_count() -> None:
    """replan 빌더는 사유 추론 + replan_count 포함."""
    state = _state(plan_stale=True, replan_count=2, subtasks=[{"description": "x"}])
    evt = build_plan_replanned("s1", state)
    assert evt.replan_count == 2
    assert "정체" in evt.reason


def test_build_step_observed_counts_selector_map() -> None:
    """observe 빌더는 selector_map 크기를 interactive_count 로 옮긴다."""
    state = _state(
        iterations=3,
        current_url="https://example.com",
        screenshot_path="/tmp/x.png",
        selector_map={0: {}, 1: {}, 2: {}, 3: {}},
    )
    evt = build_step_observed("s1", state)
    assert evt.iteration == 3
    assert evt.current_url == "https://example.com"
    assert evt.screenshot_path == "/tmp/x.png"
    assert evt.interactive_count == 4


def test_build_step_thinking_returns_none_when_history_empty() -> None:
    """history_items 가 비어 있으면 None 반환(이벤트 발행 스킵 신호)."""
    assert build_step_thinking("s1", _state(history_items=[])) is None


def test_build_step_thinking_uses_last_history_item() -> None:
    """think 빌더는 마지막 history_item 만 사용한다."""
    state = _state(
        history_items=[
            {"step": 1, "thought": "old", "action": {"name": "x"}, "memory_update": None},
            {"step": 2, "thought": "new", "action": {"name": "y"}, "memory_update": "noted"},
        ]
    )
    evt = build_step_thinking("s1", state)
    assert evt is not None
    assert evt.iteration == 2
    assert evt.thought == "new"
    assert evt.action == {"name": "y"}
    assert evt.memory_update == "noted"


def test_build_step_acted_unpacks_last_action_result() -> None:
    """act 빌더는 last_action_result 의 success/error 필드를 풀어낸다."""
    state = _state(
        iterations=4,
        last_action="click(index=12)",
        last_action_result={
            "success": False,
            "error_code": "element_not_found",
            "error_message": "요소 없음",
            "extracted": None,
            "recovery_hint": None,
        },
    )
    evt = build_step_acted("s1", state)
    assert evt.action == "click(index=12)"
    assert evt.success is False
    assert evt.error_code == "element_not_found"
    assert evt.error_message == "요소 없음"


def test_build_step_acted_handles_missing_result() -> None:
    """last_action_result 가 None 이어도 예외 없이 success=False 로 만든다."""
    evt = build_step_acted("s1", _state(last_action_result=None))
    assert evt.success is False
    assert evt.error_code is None


def test_build_step_verified_passes_through_flags() -> None:
    """verify 빌더는 is_done 과 consecutive_errors 를 그대로 옮긴다."""
    state = _state(iterations=5, is_done=True, consecutive_errors=2)
    evt = build_step_verified("s1", state)
    assert evt.is_done is True
    assert evt.consecutive_errors == 2


def test_build_subtask_activated_pulls_description_by_index() -> None:
    """subtasks 와 인덱스를 받아 해당 description 으로 이벤트를 만든다."""
    subtasks = [
        {"description": "first", "done": True},
        {"description": "second", "done": False},
    ]
    evt = build_subtask_activated("s1", subtasks, 1)
    assert evt.index == 1
    assert evt.description == "second"
