"""상호작용 액션 - 클릭, 입력, 대기."""

from playwright.async_api import Page

from core.actions._registry import registry

_MAX_WAIT_SECONDS = 10.0


@registry.register("click")
async def click(page: Page, action: dict) -> None:
    """target 텍스트로 요소를 찾아 클릭한다.

    get_by_text → get_by_role → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "click", "value": "<target>"}
    """
    target = action["value"]
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


@registry.register("type")
async def type_text(page: Page, action: dict) -> None:
    """입력 필드를 찾아 텍스트를 입력한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "type", "target": "<field>", "value": "<text>"}
    """
    target = action["target"]
    text = action["value"]
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


@registry.register("wait")
async def wait(page: Page, action: dict) -> None:
    """지정한 시간만큼 대기한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "wait", "value": <seconds: float>}
    """
    clamped = min(action["value"], _MAX_WAIT_SECONDS)
    await page.wait_for_timeout(clamped * 1_000)


@registry.register("press")
async def press(page: Page, action: dict) -> None:
    """키보드 키를 누른다.

    target이 없으면 현재 포커스된 요소에 키를 입력하고,
    target이 있으면 해당 요소를 찾아 포커스 후 키를 입력한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "press", "value": "<key>"}
              또는 {"type": "press", "value": "<key>", "target": "<element>"}

    Raises:
        RuntimeError: target이 지정되었으나 요소를 찾을 수 없는 경우
    """
    key = action["value"]
    target = action.get("target")
    timeout = 10_000

    if target is None:
        await page.keyboard.press(key)
        return

    for locator in [
        page.get_by_text(target, exact=False),
        page.get_by_role("button", name=target),
        page.locator(target),
    ]:
        try:
            await locator.first.press(key, timeout=timeout)
            return
        except Exception:
            continue

    raise RuntimeError(f"키 입력할 요소를 찾을 수 없습니다: '{target}'")
