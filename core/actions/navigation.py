"""네비게이션 액션 - URL 이동 및 스크롤."""

import os
import time

from playwright.async_api import Page

from core.actions._registry import registry

_SCREENSHOT_DIR = ".screenshots"


@registry.register("navigate")
async def navigate(page: Page, action: dict) -> None:
    """URL로 이동한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "navigate", "value": "<url>"}
    """
    await page.goto(action["value"], timeout=30_000, wait_until="domcontentloaded")


@registry.register("scroll")
async def scroll(page: Page, action: dict) -> None:
    """페이지를 스크롤한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "scroll", "value": "up" | "down"}
    """
    direction = action["value"]
    delta = 500 if direction == "down" else -500
    await page.evaluate(f"window.scrollBy(0, {delta})")


@registry.register("screenshot")
async def screenshot(page: Page, action: dict) -> None:
    """현재 페이지의 스크린샷을 저장한다.

    observe 노드의 자동 스크린샷과 별개로, 특정 시점에 수동으로 저장할 때 사용한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "screenshot"} 또는 {"type": "screenshot", "filename": "name.png"}

    Raises:
        RuntimeError: 스크린샷 저장에 실패한 경우
    """
    filename: str = action.get("filename") or f"manual_{int(time.time())}.png"
    os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(_SCREENSHOT_DIR, filename)
    try:
        await page.screenshot(path=path)
    except Exception as e:
        raise RuntimeError(f"스크린샷 저장 실패: {e}")


@registry.register("scroll_to_element")
async def scroll_to_element(page: Page, action: dict) -> None:
    """특정 요소가 화면에 보이도록 스크롤한다.

    get_by_text → get_by_role → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "scroll_to_element", "value": "스크롤할 요소 텍스트"}

    Raises:
        RuntimeError: 모든 locator 전략이 실패한 경우
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
            return
        except Exception:
            continue

    raise RuntimeError(f"스크롤할 요소를 찾을 수 없습니다: '{target}'")


@registry.register("refresh")
async def refresh(page: Page, _action: dict) -> None:
    """현재 페이지를 새로고침한다.

    Args:
        page: 현재 Playwright 페이지
        _action: {"type": "refresh"} (사용되지 않음)
    """
    await page.reload(timeout=30_000, wait_until="domcontentloaded")


@registry.register("back")
async def back(page: Page, action: dict) -> None:
    """이전 페이지로 돌아간다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "back"} 또는 {"type": "back", "count": <횟수>}
    """
    count = action.get("count", 1)
    for _ in range(count):
        await page.go_back(timeout=10_000)
