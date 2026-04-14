from core.state import AgentState

MAX_LOOP_ITERATIONS = 200
MAX_CONSECUTIVE_ERRORS = 3


async def verify(state: AgentState) -> AgentState:
    """act 실행 후 결과를 검증하고 루프 종료 여부를 판단한다.

    The Loop의 네 번째 노드. 아래 순서로 종료 조건을 확인한다:
    1. iterations가 MAX_LOOP_ITERATIONS를 초과하면 비정상 종료
    2. think에서 is_done=True로 판단했으면 정상 종료
    3. error가 있고 consecutive_errors < MAX_CONSECUTIVE_ERRORS이면
       에러를 last_action_error에 저장하고 루프 계속 (에러 복구 시도)
    4. error가 있고 consecutive_errors >= MAX_CONSECUTIVE_ERRORS이면 에러 종료
    5. 위 조건 모두 해당 없으면 루프 계속 (consecutive_errors 리셋)

    Args:
        state: 현재 에이전트 상태

    Returns:
        is_done, error, result, consecutive_errors, last_action_error가 업데이트된 AgentState.
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

        if state.get("error"):
            consecutive = state.get("consecutive_errors", 0) + 1
            if consecutive >= MAX_CONSECUTIVE_ERRORS:
                return {
                    **state,
                    "is_done": True,
                    "consecutive_errors": consecutive,
                }
            return {
                **state,
                "is_done": False,
                "consecutive_errors": consecutive,
                "last_action_error": state["error"],
                "error": None,
            }

        return {
            **state,
            "is_done": False,
            "consecutive_errors": 0,
            "last_action_error": None,
        }

    except Exception as e:
        return {**state, "is_done": True, "error": f"[verify] Unexpected error: {e}"}
