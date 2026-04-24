import json
from typing import Any, Optional

from core.state import AgentState

MAX_LOOP_ITERATIONS = 20
MAX_CONSECUTIVE_ERRORS = 3

# ── LoopDetector 상수 ────────────────────────────────────────────────────────
# 최근 N회가 동일 시그니처면 경고 (last_action_error에 힌트 주입)
LOOP_WARN_THRESHOLD = 3
# 최근 N회가 동일 시그니처면 강제 종료 (is_done=True)
LOOP_STOP_THRESHOLD = 4
# action_history에 보관할 최근 시그니처 개수
ACTION_HISTORY_MAX = 10

# 시그니처에 포함할 액션 파라미터 키. 부수 파라미터(timeout, count 등)는 제외한다.
_SIG_KEY_FIELDS = ("index", "value", "target", "source")
# 시그니처에 포함할 각 파라미터 값의 최대 길이. 긴 value로 시그니처가 부풀지 않도록.
_SIG_VALUE_MAX = 40

_LOOP_WARNING_MSG = (
    f"최근 {LOOP_WARN_THRESHOLD}회 연속 같은 액션을 수행했습니다. "
    "현재 접근이 막혀 있을 수 있습니다. 같은 요소 대신 다른 인덱스·요소를 시도하거나, "
    "scroll·URL 직접 이동 등 다른 전략을 선택하세요. 진전이 없다고 판단하면 "
    "is_done=true + result로 조기 종료도 고려하세요."
)


async def verify(state: AgentState) -> AgentState:
    """act 실행 후 결과를 검증하고 루프 종료 여부를 판단한다.

    The Loop의 네 번째 노드. 아래 순서로 종료/진행 조건을 확인한다:

    1. iterations가 MAX_LOOP_ITERATIONS를 초과하면 비정상 종료
    2. think에서 is_done=True로 판단했으면 정상 종료
    3. 액션 시그니처를 action_history에 누적하고 반복 패턴을 감지
       - stop 판정(LOOP_STOP_THRESHOLD 회 연속 동일): 강제 종료
       - warn 판정(LOOP_WARN_THRESHOLD 회 연속 동일): last_action_error에 힌트 주입
    4. error가 있고 consecutive_errors < MAX_CONSECUTIVE_ERRORS이면
       에러를 last_action_error에 저장하고 루프 계속 (에러 복구 시도). warn이
       겹치면 메시지에 루프 경고를 병합.
    5. error가 있고 consecutive_errors >= MAX_CONSECUTIVE_ERRORS이면 에러 종료
    6. 위 조건 모두 해당 없으면 루프 계속 (consecutive_errors 리셋). warn이면
       last_action_error에 경고만 주입.

    Args:
        state: 현재 에이전트 상태

    Returns:
        is_done, error, result, consecutive_errors, last_action_error,
        action_history가 업데이트된 AgentState.
    """
    try:
        if state["iterations"] > MAX_LOOP_ITERATIONS:
            return {
                **state,
                "is_done": True,
                "error": f"[verify] 최대 반복 횟수({MAX_LOOP_ITERATIONS})를 초과했습니다.",
                "result": "최대 반복 횟수를 초과했습니다.",
            }

        if state["is_done"]:
            return state

        new_history = _update_action_history(
            state.get("action_history", []),
            _action_signature(state.get("last_action")),
        )
        loop_state = _detect_loop(new_history)

        if loop_state == "stop":
            return {
                **state,
                "action_history": new_history,
                "is_done": True,
                "error": (
                    f"[verify] 동일 액션이 {LOOP_STOP_THRESHOLD}회 연속 감지되어 "
                    "루프로 판단하고 강제 종료합니다."
                ),
                "result": "동일 액션 반복으로 강제 종료했습니다.",
            }

        if state.get("error"):
            consecutive = state.get("consecutive_errors", 0) + 1
            recovery_msg: str = state["error"]  # type: ignore[assignment]
            if loop_state == "warn":
                recovery_msg = _merge_loop_warning(recovery_msg)
            if consecutive >= MAX_CONSECUTIVE_ERRORS:
                return {
                    **state,
                    "action_history": new_history,
                    "is_done": True,
                    "consecutive_errors": consecutive,
                }
            return {
                **state,
                "action_history": new_history,
                "is_done": False,
                "consecutive_errors": consecutive,
                "last_action_error": recovery_msg,
                "error": None,
            }

        return {
            **state,
            "action_history": new_history,
            "is_done": False,
            "consecutive_errors": 0,
            "last_action_error": _LOOP_WARNING_MSG if loop_state == "warn" else None,
        }

    except Exception as e:
        return {**state, "is_done": True, "error": f"[verify] Unexpected error: {e}"}


def _action_signature(last_action: Optional[str]) -> Optional[str]:
    """last_action JSON 문자열에서 반복 감지용 시그니처를 추출한다.

    type과 주요 식별 파라미터(index/value/target/source)만 포함한다. timeout처럼
    같은 의도를 가진 액션끼리 달라질 수 있는 부수 파라미터는 무시한다.

    Args:
        last_action: state["last_action"] (JSON 문자열).

    Returns:
        "type:param1:param2" 형태의 시그니처. 파싱 불가 또는 None 입력이면 None.
    """
    if not last_action:
        return None
    try:
        action = json.loads(last_action)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(action, dict):
        return None
    action_type = action.get("type", "unknown")
    parts: list[str] = [str(action_type)]
    for key in _SIG_KEY_FIELDS:
        if key in action:
            value = str(action[key])
            if len(value) > _SIG_VALUE_MAX:
                value = value[:_SIG_VALUE_MAX]
            parts.append(value)
    return ":".join(parts)


def _update_action_history(history: list[str], signature: Optional[str]) -> list[str]:
    """새 시그니처를 history에 append하고 최근 ACTION_HISTORY_MAX개로 트림한다.

    signature가 None이면 history를 그대로 반환한다(파싱 실패 액션은 집계 제외).

    Args:
        history: 기존 action_history 리스트.
        signature: _action_signature 결과.

    Returns:
        새 리스트. 원본을 변경하지 않는다.
    """
    if signature is None:
        return list(history)
    return (list(history) + [signature])[-ACTION_HISTORY_MAX:]


def _detect_loop(action_history: list[str]) -> Optional[str]:
    """최근 action_history에서 반복 패턴을 감지한다.

    단순한 "직전 N회 연속 동일" 패턴만 감지한다. A-B-A-B 교차 패턴 등은
    추적하지 않는다(필요 시 후속).

    Args:
        action_history: 최신이 끝에 있는 시그니처 리스트.

    Returns:
        "stop" — LOOP_STOP_THRESHOLD 회 연속 동일.
        "warn" — LOOP_WARN_THRESHOLD 회 연속 동일.
        None  — 반복 없음 또는 충분한 데이터 없음.
    """
    if len(action_history) < LOOP_WARN_THRESHOLD:
        return None

    last = action_history[-1]

    if len(action_history) >= LOOP_STOP_THRESHOLD:
        stop_tail = action_history[-LOOP_STOP_THRESHOLD:]
        if all(sig == last for sig in stop_tail):
            return "stop"

    warn_tail = action_history[-LOOP_WARN_THRESHOLD:]
    if all(sig == last for sig in warn_tail):
        return "warn"
    return None


def _merge_loop_warning(existing_error: str) -> str:
    """기존 act 에러 메시지에 루프 경고를 병합한다.

    Args:
        existing_error: 직전 액션 에러 문자열.

    Returns:
        기존 에러 + 빈 줄 + 루프 경고가 결합된 문자열.
    """
    return f"{existing_error}\n\n[루프 경고] {_LOOP_WARNING_MSG}"
