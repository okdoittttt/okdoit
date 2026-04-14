import json
from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from core.browser import BrowserManager
from core.state import AgentState
from core.actions import registry


async def act(state: AgentState) -> AgentState:
    """last_action을 읽어서 실제 Playwright 명령으로 변환하고 실행한다.

    The Loop의 세 번째 노드. think 노드가 결정한 액션 문자열을 파싱해서
    브라우저에 실행하고 iterations를 1 증가시킨다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        iterations가 1 증가한 AgentState.
        에러 발생 시 error 필드에 메시지를 기록하고 반환한다.
    """
    if state["is_done"]:
        return {**state, "iterations": state["iterations"] + 1}

    try:
        manager = BrowserManager()
        page = await manager.get_page()

        action = _parse_action(state["last_action"] or "")
        if "error" in action:
            return {**state, "error": action["error"], "iterations": state["iterations"] + 1}

        extracted = await _execute(page, action)

        return {
            **state,
            "error": None,
            "extracted_result": extracted,
            "iterations": state["iterations"] + 1,
        }
    except PlaywrightTimeoutError as e:
        return {**state, "error": f"[act] Timeout: {e}", "iterations": state["iterations"] + 1}
    except RuntimeError as e:
        return {**state, "error": f"[act] Browser not ready: {e}", "iterations": state["iterations"] + 1}
    except Exception as e:
        return {**state, "error": f"[act] Unexpected error: {e}", "iterations": state["iterations"] + 1}


def _parse_action(action: str) -> dict:
    """last_action JSON 문자열을 파싱해서 액션 딕셔너리를 반환한다.

    Args:
        action: think 노드가 json.dumps()로 직렬화한 액션 JSON 문자열

    Returns:
        액션 딕셔너리. 파싱 실패 시 {"error": "..."} 를 반환한다.
    """
    try:
        parsed = json.loads(action)
    except (json.JSONDecodeError, TypeError):
        return {"error": f"[act] 액션 JSON 파싱 실패: '{action}'"}

    if "type" not in parsed:
        return {"error": f"[act] 액션에 type 필드가 없습니다: '{action}'"}

    return parsed


async def _execute(page: Page, action: dict) -> Optional[str]:
    """파싱된 액션을 registry를 통해 실행하고 결과를 반환한다.

    Args:
        page: 현재 Playwright 페이지
        action: _parse_action()이 반환한 액션 딕셔너리

    Returns:
        액션 핸들러가 반환한 문자열. extract/execute_js 등 데이터 반환 액션에서만 값이 있다.

    Raises:
        ValueError: 등록되지 않은 액션 타입인 경우
    """
    return await registry.dispatch(page, action)
