from core.state import AgentState

MAX_LOOP_ITERATIONS = 20


async def verify(state: AgentState) -> AgentState:
    """act 실행 후 결과를 검증하고 루프 종료 여부를 판단한다.

    The Loop의 네 번째 노드. 아래 순서로 종료 조건을 확인한다:
    1. error가 있으면 즉시 반환 (에러 종료)
    2. iterations가 MAX_LOOP_ITERATIONS를 초과하면 비정상 종료
    3. think에서 is_done=True로 판단했으면 정상 종료
    4. 위 조건 모두 해당 없으면 루프 계속

    Args:
        state: 현재 에이전트 상태

    Returns:
        is_done, error, result이 업데이트된 AgentState.
    """
    try:
        if state.get("error"):
            return {**state, "is_done": True}

        if state["iterations"] > MAX_LOOP_ITERATIONS:
            return {
                **state,
                "is_done": True,
                "error": f"[verify] 최대 반복 횟수({MAX_LOOP_ITERATIONS})를 초과했습니다.",
                "result": "최대 반복 횟수를 초과했습니다.",
            }

        if state["is_done"]:
            return state

        return {**state, "is_done": False}

    except Exception as e:
        return {**state, "is_done": True, "error": f"[verify] Unexpected error: {e}"}
