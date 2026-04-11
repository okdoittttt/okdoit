import json

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from core.browser import BrowserManager
from core.state import AgentState

_MAX_WAIT_SECONDS = 10.0


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

        await _execute(page, action)

        return {**state, "error": None, "iterations": state["iterations"] + 1}
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


async def _execute(page: Page, action: dict) -> None:
    """파싱된 액션을 Playwright 명령으로 실행한다.

    Args:
        page: 현재 Playwright 페이지
        action: _parse_action()이 반환한 액션 딕셔너리
    """
    action_type = action["type"]

    if action_type == "navigate":
        await _navigate(page, action["value"])
    elif action_type == "click":
        await _click(page, action["value"])
    elif action_type == "type":
        await _type(page, action["target"], action["value"])
    elif action_type == "scroll":
        await _scroll(page, action["value"])
    elif action_type == "wait":
        await _wait(page, action["value"])


async def _navigate(page: Page, url: str) -> None:
    """URL로 이동한다.

    Args:
        page: 현재 Playwright 페이지
        url: 이동할 URL
    """
    await page.goto(url, timeout=30_000, wait_until="domcontentloaded")


async def _click(page: Page, target: str) -> None:
    """target 텍스트로 요소를 찾아 클릭한다.

    get_by_text → get_by_role → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        target: 클릭할 요소의 텍스트 또는 레이블
    """
    timeout = 10_000

    for locator in [
        page.get_by_text(target, exact=False),
        page.get_by_role("button", name=target),
        page.locator(target),
    ]:
        try:
            await locator.first.click(timeout=timeout)
            await page.wait_for_load_state("domcontentloaded")
            return
        except Exception:
            continue

    raise RuntimeError(f"클릭할 요소를 찾을 수 없습니다: '{target}'")


async def _type(page: Page, target: str, text: str) -> None:
    """입력 필드를 찾아 텍스트를 입력한다.

    Args:
        page: 현재 Playwright 페이지
        target: 입력 필드의 placeholder 또는 레이블
        text: 입력할 텍스트
    """
    timeout = 10_000

    for locator in [
        page.get_by_placeholder(target),
        page.get_by_label(target),
        page.get_by_role("searchbox"),
        page.get_by_role("textbox"),
        page.locator("input[type='search']"),
        page.locator("input[name='q']"),
        page.locator("textarea[name='q']"),
        page.locator(target),
    ]:
        try:
            await locator.first.clear(timeout=timeout)
            await locator.first.fill(text, timeout=timeout)
            await locator.first.press("Enter")
            return
        except Exception:
            continue

    raise RuntimeError(f"입력 필드를 찾을 수 없습니다: '{target}'")


async def _scroll(page: Page, direction: str) -> None:
    """페이지를 스크롤한다.

    Args:
        page: 현재 Playwright 페이지
        direction: "up" 또는 "down"
    """
    delta = 500 if direction == "down" else -500
    await page.evaluate(f"window.scrollBy(0, {delta})")


async def _wait(page: Page, seconds: float) -> None:
    """지정한 시간만큼 대기한다.

    Args:
        page: 현재 Playwright 페이지
        seconds: 대기할 시간 (초). 최대 10초로 제한한다.
    """
    clamped = min(seconds, _MAX_WAIT_SECONDS)
    await page.wait_for_timeout(clamped * 1_000)
