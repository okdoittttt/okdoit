"""``plan.*`` / ``subtask.*`` 이벤트들 — 계획 생성 및 진행."""

from __future__ import annotations

from typing import Any, Literal

from server.internal.events.base import BaseEvent


class PlanCreated(BaseEvent):
    """plan 노드가 초기 subtasks 를 생성했을 때 발행된다.

    Attributes:
        subtasks: ``{"index": int, "description": str, "done": bool}`` 의 리스트.
    """

    type: Literal["plan.created"] = "plan.created"
    subtasks: list[dict[str, Any]]


class PlanReplanned(BaseEvent):
    """replan 노드가 새 subtasks 로 통째 교체했을 때 발행된다.

    Attributes:
        reason: replan 트리거 사유. 현재는 자유 문자열(추후 enum 화 가능).
        replan_count: 누적 replan 횟수.
        subtasks: 교체된 subtasks.
    """

    type: Literal["plan.replanned"] = "plan.replanned"
    reason: str
    replan_count: int
    subtasks: list[dict[str, Any]]


class SubtaskActivated(BaseEvent):
    """verify 가 다음 subtask 로 active 인덱스를 옮겼을 때 발행된다.

    Attributes:
        index: 새로 활성화된 subtask 의 0-based 인덱스.
        description: 해당 subtask 의 설명 문자열.
    """

    type: Literal["subtask.activated"] = "subtask.activated"
    index: int
    description: str
