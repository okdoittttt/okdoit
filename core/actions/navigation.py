"""네비게이션 액션 - URL 이동 및 스크롤."""

import os
import time

from playwright.async_api import Page

from core.actions._registry import registry
from core.actions.result import ActionErrorCode, ActionResult

_SCREENSHOT_DIR = ".screenshots"
_INDEX_ACTION_TIMEOUT_MS = 10_000


@registry.register("navigate")
async def navigate(page: Page, action: dict) -> ActionResult:
    """URL로 이동한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "navigate", "value": "<url>"}

    Returns:
        ActionResult. 실패 시 예외를 그대로 던진다(registry가 매핑).
    """
    await page.goto(action["value"], timeout=30_000, wait_until="domcontentloaded")
    return ActionResult.ok()


@registry.register("scroll")
async def scroll(page: Page, action: dict) -> ActionResult:
    """페이지를 스크롤한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "scroll", "value": "up" | "down"}

    Returns:
        ActionResult.
    """
    direction = action["value"]
    delta = 500 if direction == "down" else -500
    await page.evaluate(f"window.scrollBy(0, {delta})")
    return ActionResult.ok()


@registry.register("screenshot")
async def screenshot(page: Page, action: dict) -> ActionResult:
    """현재 페이지의 스크린샷을 저장한다.

    observe 노드의 자동 스크린샷과 별개로, 특정 시점에 수동으로 저장할 때 사용한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "screenshot"} 또는 {"type": "screenshot", "filename": "name.png"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 스크린샷 저장에 실패한 경우 (registry가 UNKNOWN으로 매핑).
    """
    filename: str = action.get("filename") or f"manual_{int(time.time())}.png"
    os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(_SCREENSHOT_DIR, filename)
    try:
        await page.screenshot(path=path)
    except Exception as e:
        raise RuntimeError(f"스크린샷 저장 실패: {e}")
    return ActionResult.ok()


@registry.register("scroll_to_element")
async def scroll_to_element(page: Page, action: dict) -> ActionResult:
    """특정 요소가 화면에 보이도록 스크롤한다.

    get_by_text → get_by_role → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "scroll_to_element", "value": "스크롤할 요소 텍스트"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 모든 locator 전략이 실패한 경우 (ELEMENT_NOT_FOUND).
    """
    target: str = action["value"]
    timeout = 10_000

    for locator in [
        page.get_by_text(target, exact=False),
        page.get_by_role("button", name=target),
        page.locator(target),
    ]:
        try:
            await locator.first.scroll_into_view_if_needed(timeout=timeout)
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"스크롤할 요소를 찾을 수 없습니다: '{target}'")


@registry.register("refresh")
async def refresh(page: Page, _action: dict) -> ActionResult:
    """현재 페이지를 새로고침한다.

    Args:
        page: 현재 Playwright 페이지
        _action: {"type": "refresh"} (사용되지 않음)

    Returns:
        ActionResult.
    """
    await page.reload(timeout=30_000, wait_until="domcontentloaded")
    return ActionResult.ok()


@registry.register("back")
async def back(page: Page, action: dict) -> ActionResult:
    """이전 페이지로 돌아간다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "back"} 또는 {"type": "back", "count": <횟수>}

    Returns:
        ActionResult.
    """
    count = action.get("count", 1)
    for _ in range(count):
        await page.go_back(timeout=10_000)
    return ActionResult.ok()


@registry.register("scroll_to_index")
async def scroll_to_index(page: Page, action: dict) -> ActionResult:
    """인덱스로 지정된 요소가 뷰포트에 보이도록 스크롤한다.

    observe가 인덱싱한 요소가 뷰포트 바깥에 있을 때 사용한다. 일반 ``scroll`` 과
    달리 정확한 요소를 타겟으로 한다.

    Args:
        page: 현재 Playwright 페이지.
        action: ``{"type": "scroll_to_index", "index": <int>}``.

    Returns:
        ActionResult. 인덱스에 해당하는 요소가 없으면 ELEMENT_NOT_FOUND로 실패.
    """
    idx = int(action["index"])
    loc = page.locator(f'[data-oi-idx="{idx}"]')
    if await loc.count() == 0:
        return ActionResult.fail(
            ActionErrorCode.ELEMENT_NOT_FOUND,
            (
                f"인덱스 {idx}의 요소가 현재 DOM에 없습니다. 페이지가 전환되었거나 "
                "observe 이후 DOM이 변경됐을 수 있습니다."
            ),
        )
    await loc.first.scroll_into_view_if_needed(timeout=_INDEX_ACTION_TIMEOUT_MS)
    return ActionResult.ok()
