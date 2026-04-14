"""네비게이션 액션 - URL 이동 및 스크롤."""

from playwright.async_api import Page

from core.actions._registry import registry


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


@registry.register("refresh")
async def refresh(page: Page, action: dict) -> None:
    """현재 페이지를 새로고침한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "refresh"}
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
