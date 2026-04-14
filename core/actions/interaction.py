"""상호작용 액션 - 클릭, 입력, 대기."""

from playwright.async_api import Page

from core.actions._registry import registry

_MAX_WAIT_SECONDS = 10.0
_MAX_WAIT_ELEMENT_SECONDS = 30.0
_DEFAULT_ELEMENT_TIMEOUT_SECONDS = 15.0
_VALID_CHECK_STATES = frozenset({"check", "uncheck"})


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


@registry.register("hover")
async def hover(page: Page, action: dict) -> None:
    """target 텍스트로 요소를 찾아 마우스를 올린다 (hover).

    get_by_text → get_by_role → locator 순서로 시도한다.
    툴팁 표시, 드롭다운 펼치기 등 마우스 오버 이벤트 유발에 사용한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "hover", "value": "<target>"}

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
            await locator.first.hover(timeout=timeout)
            return
        except Exception:
            continue

    raise RuntimeError(f"호버할 요소를 찾을 수 없습니다: '{target}'")


@registry.register("wait_for_element")
async def wait_for_element(page: Page, action: dict) -> None:
    """특정 요소가 페이지에 나타날 때까지 대기한다.

    get_by_text → locator 순서로 시도하며, 요소가 visible 상태가 될 때까지 기다린다.
    동적으로 렌더링되는 요소 대기, SPA 라우팅 완료 확인 등에 사용한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "wait_for_element", "value": "<target>"}
                또는 {"type": "wait_for_element", "value": "<target>", "timeout": <seconds>}

    Raises:
        RuntimeError: 지정된 시간 내 요소가 나타나지 않은 경우
    """
    target: str = action["value"]
    raw_timeout: float = float(action.get("timeout", _DEFAULT_ELEMENT_TIMEOUT_SECONDS))
    timeout_ms: int = int(min(raw_timeout, _MAX_WAIT_ELEMENT_SECONDS) * 1_000)

    for locator in [
        page.get_by_text(target, exact=False),
        page.locator(target),
    ]:
        try:
            await locator.first.wait_for(state="visible", timeout=timeout_ms)
            return
        except Exception:
            continue

    raise RuntimeError(f"요소가 나타나지 않습니다: '{target}' ({raw_timeout}초 초과)")


@registry.register("check")
async def check(page: Page, action: dict) -> None:
    """체크박스 또는 라디오 버튼을 지정한 상태로 설정한다.

    state가 "check"이면 선택, "uncheck"이면 해제한다.
    get_by_label → get_by_text → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "check", "value": "<target>"}
                또는 {"type": "check", "value": "<target>", "state": "check" | "uncheck"}

    Raises:
        ValueError: state 값이 "check" 또는 "uncheck"가 아닌 경우
        RuntimeError: 모든 locator 전략이 실패한 경우
    """
    target: str = action["value"]
    state: str = action.get("state", "check")
    timeout = 10_000

    if state not in _VALID_CHECK_STATES:
        raise ValueError(f"check 액션의 state는 'check' 또는 'uncheck'여야 합니다: '{state}'")

    for locator in [
        page.get_by_label(target),
        page.get_by_text(target, exact=False),
        page.locator(target),
    ]:
        try:
            if state == "check":
                await locator.first.check(timeout=timeout)
            else:
                await locator.first.uncheck(timeout=timeout)
            return
        except Exception:
            continue

    raise RuntimeError(f"체크박스/라디오를 찾을 수 없습니다: '{target}'")
