"""``AgentState`` → ``ServerEvent`` 변환을 위한 순수 함수 모음.

각 ``build_*`` 함수는 그래프 노드가 반환한 state dict 와 session_id 를 받아
대응하는 ``ServerEvent`` 를 만든다. 부수효과 없음(asyncio/Session/IO 의존성 0).

``AgentRunner`` 는 이 함수들을 호출해 결과를 ``Session.publish`` 로 흘려보낸다.
이 분리는 두 가지 이득을 준다:
    - AgentRunner 가 흐름 제어에만 집중할 수 있어 짧고 읽기 쉽다.
    - 빌더는 dict 입력 / dataclass 출력의 순수 함수라 단위 테스트가 쉽다.
"""

from __future__ import annotations

from typing import Any, Optional

from core.state import AgentState
from server.internal.events import (
    PlanCreated,
    PlanReplanned,
    StepActed,
    StepObserved,
    StepThinking,
    StepVerified,
    SubtaskActivated,
)


# ── 헬퍼 ────────────────────────────────────────────────────────


def normalize_subtasks(subtasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``subtasks`` 리스트에 ``index`` 필드를 보강해 UI 친화 형태로 만든다.

    Args:
        subtasks: ``core/state.py`` 가 보장하는 ``[{"description", "done"}]``.

    Returns:
        ``[{"index", "description", "done"}]`` 형태. 빈 리스트면 빈 리스트.
    """
    return [
        {
            "index": i,
            "description": str(item.get("description", "")),
            "done": bool(item.get("done", False)),
        }
        for i, item in enumerate(subtasks)
    ]


def find_active_subtask_index(subtasks: list[dict[str, Any]]) -> int:
    """첫 번째 not-done subtask 인덱스를 반환한다. 없으면 -1.

    Args:
        subtasks: ``[{"description", "done", ...}]`` 리스트.

    Returns:
        active 인덱스 또는 -1 (모두 완료 / 빈 리스트).
    """
    for i, item in enumerate(subtasks):
        if not item.get("done"):
            return i
    return -1


def infer_replan_reason(state: AgentState) -> str:
    """현재 상태로부터 replan 트리거 사유를 추정한다.

    Args:
        state: replan 노드가 반환한 직후의 상태.

    Returns:
        UI 에 노출할 짧은 한국어 사유 문자열.
    """
    if state.get("plan_stale"):
        return "계획 진행이 정체되어 재계획"
    return "이전 계획 완료 후 추가 단계 필요"


# ── 노드별 빌더 ─────────────────────────────────────────────────


def build_plan_created(session_id: str, state: AgentState) -> PlanCreated:
    """plan 노드 결과를 ``PlanCreated`` 이벤트로 변환한다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        state: plan 노드가 반환한 ``AgentState``.

    Returns:
        ``PlanCreated`` 인스턴스.
    """
    return PlanCreated(
        session_id=session_id,
        subtasks=normalize_subtasks(state.get("subtasks", [])),
    )


def build_plan_replanned(session_id: str, state: AgentState) -> PlanReplanned:
    """replan 노드 결과를 ``PlanReplanned`` 이벤트로 변환한다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        state: replan 노드가 반환한 ``AgentState``.

    Returns:
        ``PlanReplanned`` 인스턴스.
    """
    return PlanReplanned(
        session_id=session_id,
        reason=infer_replan_reason(state),
        replan_count=int(state.get("replan_count", 0)),
        subtasks=normalize_subtasks(state.get("subtasks", [])),
    )


def build_step_observed(session_id: str, state: AgentState) -> StepObserved:
    """observe 노드 결과를 ``StepObserved`` 이벤트로 변환한다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        state: observe 노드가 반환한 ``AgentState``.

    Returns:
        ``StepObserved`` 인스턴스.
    """
    selector_map = state.get("selector_map") or {}
    return StepObserved(
        session_id=session_id,
        iteration=int(state.get("iterations", 0)),
        current_url=str(state.get("current_url") or ""),
        screenshot_path=state.get("screenshot_path"),
        interactive_count=len(selector_map),
    )


def build_step_thinking(session_id: str, state: AgentState) -> Optional[StepThinking]:
    """think 노드 결과의 마지막 history_items 항목으로 이벤트를 만든다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        state: think 노드가 반환한 ``AgentState``.

    Returns:
        ``StepThinking`` 인스턴스. ``history_items`` 가 비어 있으면 None.
    """
    history = state.get("history_items") or []
    if not history:
        return None
    last = history[-1]
    return StepThinking(
        session_id=session_id,
        iteration=int(last.get("step", state.get("iterations", 0))),
        thought=str(last.get("thought") or ""),
        action=dict(last.get("action") or {}),
        memory_update=last.get("memory_update"),
    )


def build_step_acted(session_id: str, state: AgentState) -> StepActed:
    """act 노드의 ``last_action_result`` 를 ``StepActed`` 로 변환한다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        state: act 노드가 반환한 ``AgentState``.

    Returns:
        ``StepActed`` 인스턴스.
    """
    result = state.get("last_action_result") or {}
    return StepActed(
        session_id=session_id,
        iteration=int(state.get("iterations", 0)),
        action=str(state.get("last_action") or ""),
        success=bool(result.get("success", False)),
        error_code=result.get("error_code"),
        error_message=result.get("error_message"),
        extracted=result.get("extracted"),
    )


def build_step_verified(session_id: str, state: AgentState) -> StepVerified:
    """verify 노드 결과를 ``StepVerified`` 이벤트로 변환한다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        state: verify 노드가 반환한 ``AgentState``.

    Returns:
        ``StepVerified`` 인스턴스.
    """
    return StepVerified(
        session_id=session_id,
        iteration=int(state.get("iterations", 0)),
        is_done=bool(state.get("is_done", False)),
        consecutive_errors=int(state.get("consecutive_errors", 0)),
    )


def build_subtask_activated(
    session_id: str, subtasks: list[dict[str, Any]], index: int
) -> SubtaskActivated:
    """active subtask 가 바뀐 직후의 ``SubtaskActivated`` 이벤트를 만든다.

    Args:
        session_id: 이벤트가 속할 세션 식별자.
        subtasks: 현재 subtasks 리스트.
        index: 새로 활성화된 subtask 의 인덱스. 호출 측이 ``find_active_subtask_index``
            로 얻은 값을 그대로 넘긴다.

    Returns:
        ``SubtaskActivated`` 인스턴스.
    """
    return SubtaskActivated(
        session_id=session_id,
        index=index,
        description=str(subtasks[index].get("description", "")),
    )
