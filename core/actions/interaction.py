"""상호작용 액션 - 클릭, 입력, 대기."""

from typing import Optional

from playwright.async_api import Page

from core.actions._registry import registry
from core.browser import BrowserManager

_MAX_WAIT_SECONDS = 10.0
_MAX_WAIT_ELEMENT_SECONDS = 30.0
_DEFAULT_ELEMENT_TIMEOUT_SECONDS = 15.0
_VALID_CHECK_STATES = frozenset({"check", "uncheck"})


_NEW_TAB_WAIT_MS = 800


@registry.register("click")
async def click(page: Page, action: dict) -> None:
    """target 텍스트로 요소를 찾아 클릭한다.

    get_by_text → get_by_role → locator 순서로 시도한다.
    클릭 후 새 탭이 열리면 BrowserManager의 활성 페이지를 새 탭으로 전환한다.

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
            pages_before = list(page.context.pages)
            await locator.first.click(timeout=timeout)
            await page.wait_for_timeout(_NEW_TAB_WAIT_MS)

            new_pages = [p for p in page.context.pages if p not in pages_before]
            if new_pages:
                new_page = new_pages[-1]
                await new_page.wait_for_load_state("domcontentloaded")
                BrowserManager()._page = new_page
            else:
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


@registry.register("extract")
async def extract(page: Page, action: dict) -> Optional[str]:
    """CSS 선택자 또는 텍스트로 요소의 내용을 추출한다.

    CSS 선택자로 먼저 시도하고, 실패하면 텍스트 기반 locator로 시도한다.
    추출된 텍스트는 다음 think 사이클에서 [추출된 데이터]로 LLM에 전달된다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "extract", "value": "<CSS 선택자 또는 텍스트>"}

    Returns:
        추출된 텍스트 문자열

    Raises:
        RuntimeError: 요소를 찾을 수 없거나 추출에 실패한 경우
    """
    target: str = action["value"]

    try:
        result: str = await page.evaluate(
            """(selector) => {
                const elements = document.querySelectorAll(selector);
                if (elements.length === 0) return null;
                return Array.from(elements)
                    .map(el => (el.innerText || el.textContent || '').trim())
                    .filter(t => t.length > 0)
                    .join('\\n');
            }""",
            target,
        )
        if result:
            return result
    except Exception:
        pass

    try:
        locator = page.get_by_text(target, exact=False)
        text = await locator.first.inner_text(timeout=5_000)
        if text:
            return text.strip()
    except Exception:
        pass

    raise RuntimeError(f"extract 실패: '{target}'에 해당하는 요소를 찾을 수 없습니다")


@registry.register("execute_js")
async def execute_js(page: Page, action: dict) -> Optional[str]:
    """브라우저에서 JavaScript를 실행하고 결과를 반환한다.

    page.evaluate()를 통해 브라우저 샌드박스 내에서 실행된다.
    결과는 다음 think 사이클에서 [추출된 데이터]로 LLM에 전달된다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "execute_js", "value": "<JS 코드>"}

    Returns:
        JS 실행 결과를 문자열로 변환한 값. 결과가 None이면 빈 문자열.

    Raises:
        RuntimeError: JS 실행 중 오류가 발생한 경우
    """
    js_code: str = action["value"]
    try:
        result = await page.evaluate(js_code)
        return str(result) if result is not None else ""
    except Exception as e:
        raise RuntimeError(f"JS 실행 실패: {e}")


@registry.register("drag_and_drop")
async def drag_and_drop(page: Page, action: dict) -> None:
    """source 요소를 target 위치로 드래그 앤 드롭한다.

    텍스트 기반 locator로 먼저 시도하고, 실패하면 CSS 선택자로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "drag_and_drop", "source": "<드래그할 요소>", "target": "<드롭할 위치>"}

    Raises:
        RuntimeError: 드래그 앤 드롭에 실패한 경우
    """
    source: str = action["source"]
    target: str = action["target"]
    timeout = 10_000

    try:
        source_locator = page.get_by_text(source, exact=False).first
        target_locator = page.get_by_text(target, exact=False).first
        await source_locator.drag_to(target_locator, timeout=timeout)
        return
    except Exception:
        pass

    try:
        await page.drag_and_drop(source, target, timeout=timeout)
        return
    except Exception as e:
        raise RuntimeError(f"드래그 앤 드롭 실패: '{source}' → '{target}' - {e}")
