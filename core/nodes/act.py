import json

from core.actions import registry
from core.actions.result import ActionErrorCode, ActionResult, recovery_hint_for
from core.browser import BrowserManager
from core.state import AgentState


async def act(state: AgentState) -> AgentState:
    """last_action을 읽어서 registry.dispatch로 실행하고 state를 갱신한다.

    The Loop의 세 번째 노드. think 노드가 결정한 액션 문자열을 파싱해서 실제
    브라우저에 실행한다. 실행 결과는 ``last_action_result`` 에 구조화 dict로 저장되며,
    실패 시 프롬프트 친화적 에러 메시지가 ``error`` 에 기록된다.

    ``extracted_result`` 는 성공한 액션이 돌려준 텍스트(extract/execute_js)로 채워지고,
    실패하거나 데이터가 없으면 None이다.

    Args:
        state: 현재 에이전트 상태.

    Returns:
        last_action_result, error, extracted_result, iterations가 갱신된 AgentState.
    """
    if state["is_done"]:
        return {**state, "iterations": state["iterations"] + 1}

    action = _parse_action(state["last_action"] or "")
    if "error" in action:
        parse_fail = ActionResult.fail(
            ActionErrorCode.INVALID_ARGUMENT,
            action["error"],
            recovery_hint_for(ActionErrorCode.INVALID_ARGUMENT),
        )
        return _state_for_failure(state, parse_fail)

    try:
        manager = BrowserManager()
        page = await manager.get_page()
    except RuntimeError as e:
        browser_fail = ActionResult.fail(
            ActionErrorCode.UNKNOWN,
            f"브라우저가 준비되지 않았습니다: {e}",
            recovery_hint_for(ActionErrorCode.UNKNOWN),
        )
        return _state_for_failure(state, browser_fail)

    result = await registry.dispatch(page, action)

    if result.success:
        return {
            **state,
            "last_action_result": result.to_dict(),
            "error": None,
            "extracted_result": result.extracted,
            "iterations": state["iterations"] + 1,
        }
    return _state_for_failure(state, result)


def _state_for_failure(state: AgentState, result: ActionResult) -> AgentState:
    """실패한 ActionResult로 공통 state 패치를 구성한다.

    error 필드에는 LLM이 읽을 한 문단 메시지(메시지 + error_code + 복구 힌트)를 넣고,
    last_action_result에는 원본 구조를 저장한다.

    Args:
        state: 현재 에이전트 상태.
        result: success=False인 ActionResult.

    Returns:
        갱신된 AgentState. iterations는 1 증가한다.
    """
    return {
        **state,
        "last_action_result": result.to_dict(),
        "error": _compose_error_message(result),
        "extracted_result": None,
        "iterations": state["iterations"] + 1,
    }


def _compose_error_message(result: ActionResult) -> str:
    """ActionResult 실패를 LLM이 바로 읽을 수 있는 한 문단 메시지로 포맷한다.

    형식:
        [act] <error_message>
        error_code: <code>
        복구 힌트: <hint>

    Args:
        result: success=False인 ActionResult.

    Returns:
        세 줄 포맷의 에러 문자열. 없는 필드는 생략.
    """
    message = result.error_message or "알 수 없는 오류가 발생했습니다."
    parts: list[str] = [f"[act] {message}"]
    if result.error_code is not None:
        parts.append(f"error_code: {result.error_code.value}")
    if result.recovery_hint:
        parts.append(f"복구 힌트: {result.recovery_hint}")
    return "\n".join(parts)


def _parse_action(action: str) -> dict:
    """last_action JSON 문자열을 파싱해서 액션 딕셔너리를 반환한다.

    Args:
        action: think 노드가 json.dumps()로 직렬화한 액션 JSON 문자열.

    Returns:
        액션 딕셔너리. 파싱 실패 시 {"error": "..."} 형태로 반환한다.
    """
    try:
        parsed = json.loads(action)
    except (json.JSONDecodeError, TypeError):
        return {"error": f"[act] 액션 JSON 파싱 실패: '{action}'"}

    if "type" not in parsed:
        return {"error": f"[act] 액션에 type 필드가 없습니다: '{action}'"}

    return parsed
