"""상호작용 액션 - 클릭, 입력, 대기.

텍스트 기반 액션(``click``, ``type`` 등)과 인덱스 기반 액션(``click_index``,
``type_index`` 등)이 공존한다. LLM은 인덱스 기반을 우선 사용하고, observe가
인덱싱하지 못한 케이스(동적 요소 등)에만 텍스트 기반을 폴백으로 쓴다.

인덱스 기반 액션은 observe 노드가 브라우저에 심은 ``data-oi-idx`` 속성을
locator로 직접 지정한다. 매 턴 observe가 재부여하므로 한 턴 안에서만 유효하다.
"""

from playwright.async_api import Locator, Page

from core.actions._registry import registry
from core.actions.result import ActionErrorCode, ActionResult
from core.browser import BrowserManager

_MAX_WAIT_SECONDS = 10.0
_MAX_WAIT_ELEMENT_SECONDS = 30.0
_DEFAULT_ELEMENT_TIMEOUT_SECONDS = 15.0
_VALID_CHECK_STATES = frozenset({"check", "uncheck"})


_NEW_TAB_WAIT_MS = 800
_INDEX_ACTION_TIMEOUT_MS = 10_000


def _locator_for_index(page: Page, idx: int) -> Locator:
    """data-oi-idx 속성으로 locator를 만든다(존재 여부 체크 전 단계).

    Args:
        page: 현재 Playwright 페이지.
        idx: observe가 부여한 정수 인덱스.

    Returns:
        ``[data-oi-idx="{idx}"]`` 로 좁혀진 locator.
    """
    return page.locator(f'[data-oi-idx="{idx}"]')


async def _assert_index_exists(loc: Locator, idx: int) -> ActionResult | None:
    """인덱스에 해당하는 요소가 DOM에 존재하는지 확인한다.

    Args:
        loc: ``_locator_for_index`` 결과.
        idx: 에러 메시지용 인덱스 값.

    Returns:
        존재하면 None. 없으면 ``ActionResult.fail(ELEMENT_NOT_FOUND, ...)``.
    """
    if await loc.count() == 0:
        return ActionResult.fail(
            ActionErrorCode.ELEMENT_NOT_FOUND,
            (
                f"인덱스 {idx}의 요소가 현재 DOM에 없습니다. 페이지가 전환되었거나 "
                "observe 이후 DOM이 변경됐을 수 있습니다. 다음 턴에서 최신 인덱스를 사용하세요."
            ),
        )
    return None


@registry.register("click")
async def click(page: Page, action: dict) -> ActionResult:
    """target 텍스트로 요소를 찾아 클릭한다.

    get_by_text → get_by_role → locator 순서로 시도한다.
    클릭 후 새 탭이 열리면 BrowserManager의 활성 페이지를 새 탭으로 전환한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "click", "value": "<target>"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 모든 locator 전략이 실패한 경우 (ELEMENT_NOT_FOUND).
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
                BrowserManager.current()._page = new_page
            else:
                await page.wait_for_load_state("domcontentloaded")
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"클릭할 요소를 찾을 수 없습니다: '{target}'")


@registry.register("type")
async def type_text(page: Page, action: dict) -> ActionResult:
    """입력 필드를 찾아 텍스트를 입력한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "type", "target": "<field>", "value": "<text>"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 모든 locator 전략이 실패한 경우 (ELEMENT_NOT_FOUND).
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
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"입력 필드를 찾을 수 없습니다: '{target}'")


@registry.register("wait")
async def wait(page: Page, action: dict) -> ActionResult:
    """지정한 시간만큼 대기한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "wait", "value": <seconds: float>}

    Returns:
        ActionResult.
    """
    clamped = min(action["value"], _MAX_WAIT_SECONDS)
    await page.wait_for_timeout(clamped * 1_000)
    return ActionResult.ok()


@registry.register("press")
async def press(page: Page, action: dict) -> ActionResult:
    """키보드 키를 누른다.

    target이 없으면 현재 포커스된 요소에 키를 입력하고,
    target이 있으면 해당 요소를 찾아 포커스 후 키를 입력한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "press", "value": "<key>"}
              또는 {"type": "press", "value": "<key>", "target": "<element>"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: target이 지정되었으나 요소를 찾을 수 없는 경우.
    """
    key = action["value"]
    target = action.get("target")
    timeout = 10_000

    if target is None:
        await page.keyboard.press(key)
        return ActionResult.ok()

    for locator in [
        page.get_by_text(target, exact=False),
        page.get_by_role("button", name=target),
        page.locator(target),
    ]:
        try:
            await locator.first.press(key, timeout=timeout)
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"키 입력할 요소를 찾을 수 없습니다: '{target}'")


@registry.register("hover")
async def hover(page: Page, action: dict) -> ActionResult:
    """target 텍스트로 요소를 찾아 마우스를 올린다 (hover).

    get_by_text → get_by_role → locator 순서로 시도한다.
    툴팁 표시, 드롭다운 펼치기 등 마우스 오버 이벤트 유발에 사용한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "hover", "value": "<target>"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 모든 locator 전략이 실패한 경우.
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
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"호버할 요소를 찾을 수 없습니다: '{target}'")


@registry.register("wait_for_element")
async def wait_for_element(page: Page, action: dict) -> ActionResult:
    """특정 요소가 페이지에 나타날 때까지 대기한다.

    get_by_text → locator 순서로 시도하며, 요소가 visible 상태가 될 때까지 기다린다.
    동적으로 렌더링되는 요소 대기, SPA 라우팅 완료 확인 등에 사용한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "wait_for_element", "value": "<target>"}
                또는 {"type": "wait_for_element", "value": "<target>", "timeout": <seconds>}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 지정된 시간 내 요소가 나타나지 않은 경우.
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
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"요소가 나타나지 않습니다: '{target}' ({raw_timeout}초 초과)")


@registry.register("check")
async def check(page: Page, action: dict) -> ActionResult:
    """체크박스 또는 라디오 버튼을 지정한 상태로 설정한다.

    state가 "check"이면 선택, "uncheck"이면 해제한다.
    get_by_label → get_by_text → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "check", "value": "<target>"}
                또는 {"type": "check", "value": "<target>", "state": "check" | "uncheck"}

    Returns:
        ActionResult. state 값이 잘못된 경우 INVALID_ARGUMENT로 명시적 fail.

    Raises:
        RuntimeError: 모든 locator 전략이 실패한 경우.
    """
    target: str = action["value"]
    state: str = action.get("state", "check")
    timeout = 10_000

    if state not in _VALID_CHECK_STATES:
        return ActionResult.fail(
            ActionErrorCode.INVALID_ARGUMENT,
            f"check 액션의 state는 'check' 또는 'uncheck'여야 합니다: '{state}'",
        )

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
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"체크박스/라디오를 찾을 수 없습니다: '{target}'")


@registry.register("extract")
async def extract(page: Page, action: dict) -> ActionResult:
    """CSS 선택자 또는 텍스트로 요소의 내용을 추출한다.

    CSS 선택자로 먼저 시도하고, 실패하면 텍스트 기반 locator로 시도한다.
    추출된 텍스트는 다음 think 사이클에서 [추출된 데이터]로 LLM에 전달된다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "extract", "value": "<CSS 선택자 또는 텍스트>"}

    Returns:
        ActionResult.ok(extracted=...) — 추출된 텍스트를 담는다.

    Raises:
        RuntimeError: 요소를 찾을 수 없거나 추출에 실패한 경우.
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
            return ActionResult.ok(extracted=result)
    except Exception:
        pass

    try:
        locator = page.get_by_text(target, exact=False)
        text = await locator.first.inner_text(timeout=5_000)
        if text:
            return ActionResult.ok(extracted=text.strip())
    except Exception:
        pass

    raise RuntimeError(f"extract 실패: '{target}'에 해당하는 요소를 찾을 수 없습니다")


@registry.register("execute_js")
async def execute_js(page: Page, action: dict) -> ActionResult:
    """브라우저에서 JavaScript를 실행하고 결과를 반환한다.

    page.evaluate()를 통해 브라우저 샌드박스 내에서 실행된다.
    결과는 다음 think 사이클에서 [추출된 데이터]로 LLM에 전달된다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "execute_js", "value": "<JS 코드>"}

    Returns:
        ActionResult.ok(extracted=...) — JS 실행 결과를 문자열로 변환해 담는다.

    Raises:
        RuntimeError: JS 실행 중 오류가 발생한 경우.
    """
    js_code: str = action["value"]
    try:
        result = await page.evaluate(js_code)
    except Exception as e:
        raise RuntimeError(f"JS 실행 실패: {e}")
    return ActionResult.ok(extracted=str(result) if result is not None else "")


@registry.register("drag_and_drop")
async def drag_and_drop(page: Page, action: dict) -> ActionResult:
    """source 요소를 target 위치로 드래그 앤 드롭한다.

    텍스트 기반 locator로 먼저 시도하고, 실패하면 CSS 선택자로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "drag_and_drop", "source": "<드래그할 요소>", "target": "<드롭할 위치>"}

    Returns:
        ActionResult.

    Raises:
        RuntimeError: 드래그 앤 드롭에 실패한 경우.
    """
    source: str = action["source"]
    target: str = action["target"]
    timeout = 10_000

    try:
        source_locator = page.get_by_text(source, exact=False).first
        target_locator = page.get_by_text(target, exact=False).first
        await source_locator.drag_to(target_locator, timeout=timeout)
        return ActionResult.ok()
    except Exception:
        pass

    try:
        await page.drag_and_drop(source, target, timeout=timeout)
        return ActionResult.ok()
    except Exception as e:
        raise RuntimeError(f"드래그 앤 드롭 실패: '{source}' → '{target}' - {e}")


# ── 인덱스 기반 액션 ─────────────────────────────────────────────────────────
# observe가 심은 data-oi-idx 속성으로 요소를 직접 참조한다. 텍스트 매칭 불필요.


@registry.register("click_index")
async def click_by_index(page: Page, action: dict) -> ActionResult:
    """인덱스로 지정된 요소를 클릭한다.

    새 탭이 열리면 BrowserManager의 활성 페이지를 해당 탭으로 전환한다.

    Args:
        page: 현재 Playwright 페이지.
        action: ``{"type": "click_index", "index": <int>}``.

    Returns:
        ActionResult. 인덱스에 해당하는 요소가 없으면 ELEMENT_NOT_FOUND로 실패.
    """
    idx = int(action["index"])
    loc = _locator_for_index(page, idx)
    missing = await _assert_index_exists(loc, idx)
    if missing is not None:
        return missing

    try:
        await loc.first.scroll_into_view_if_needed(timeout=5_000)
    except Exception:
        # 스크롤 실패는 치명적이지 않다. 일부 요소(fixed, in-viewport)는 이미 보이거나
        # scroll_into_view가 불필요한 경우가 있다. 클릭을 그대로 시도한다.
        pass

    pages_before = list(page.context.pages)
    await loc.first.click(timeout=_INDEX_ACTION_TIMEOUT_MS)
    await page.wait_for_timeout(_NEW_TAB_WAIT_MS)

    new_pages = [p for p in page.context.pages if p not in pages_before]
    if new_pages:
        new_page = new_pages[-1]
        await new_page.wait_for_load_state("domcontentloaded")
        BrowserManager.current()._page = new_page
    else:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except Exception:
            pass
    return ActionResult.ok()


@registry.register("type_index")
async def type_by_index(page: Page, action: dict) -> ActionResult:
    """인덱스로 지정된 입력 필드에 텍스트를 입력한다.

    기본 동작은 기존 값을 clear 후 fill + Enter 입력이다. Enter를 누르지 않으려면
    ``"submit": false`` 를 명시한다.

    Args:
        page: 현재 Playwright 페이지.
        action: ``{"type": "type_index", "index": <int>, "value": "<text>", "submit"?: bool}``.

    Returns:
        ActionResult. 인덱스 없음은 ELEMENT_NOT_FOUND로 실패.
    """
    idx = int(action["index"])
    text = action["value"]
    submit = bool(action.get("submit", True))

    loc = _locator_for_index(page, idx)
    missing = await _assert_index_exists(loc, idx)
    if missing is not None:
        return missing

    await loc.first.clear(timeout=_INDEX_ACTION_TIMEOUT_MS)
    await loc.first.fill(text, timeout=_INDEX_ACTION_TIMEOUT_MS)
    if submit:
        await loc.first.press("Enter")
    return ActionResult.ok()


@registry.register("hover_index")
async def hover_by_index(page: Page, action: dict) -> ActionResult:
    """인덱스로 지정된 요소에 마우스를 올린다.

    Args:
        page: 현재 Playwright 페이지.
        action: ``{"type": "hover_index", "index": <int>}``.

    Returns:
        ActionResult.
    """
    idx = int(action["index"])
    loc = _locator_for_index(page, idx)
    missing = await _assert_index_exists(loc, idx)
    if missing is not None:
        return missing

    await loc.first.hover(timeout=_INDEX_ACTION_TIMEOUT_MS)
    return ActionResult.ok()


@registry.register("press_index")
async def press_by_index(page: Page, action: dict) -> ActionResult:
    """인덱스로 지정된 요소에 포커스 후 키보드 키를 입력한다.

    Args:
        page: 현재 Playwright 페이지.
        action: ``{"type": "press_index", "index": <int>, "value": "<key>"}``.
            value는 Playwright 키 이름(Enter/Escape/Tab/ArrowDown 등).

    Returns:
        ActionResult.
    """
    idx = int(action["index"])
    key = action["value"]
    loc = _locator_for_index(page, idx)
    missing = await _assert_index_exists(loc, idx)
    if missing is not None:
        return missing

    await loc.first.press(key, timeout=_INDEX_ACTION_TIMEOUT_MS)
    return ActionResult.ok()


@registry.register("check_index")
async def check_by_index(page: Page, action: dict) -> ActionResult:
    """인덱스로 지정된 체크박스/라디오를 설정한다.

    Args:
        page: 현재 Playwright 페이지.
        action: ``{"type": "check_index", "index": <int>, "state"?: "check"|"uncheck"}``.
            state 기본값은 "check".

    Returns:
        ActionResult. state 값이 잘못되면 INVALID_ARGUMENT, 요소 없음은 ELEMENT_NOT_FOUND.
    """
    idx = int(action["index"])
    state = action.get("state", "check")
    if state not in _VALID_CHECK_STATES:
        return ActionResult.fail(
            ActionErrorCode.INVALID_ARGUMENT,
            f"check_index의 state는 'check' 또는 'uncheck'여야 합니다: '{state}'",
        )

    loc = _locator_for_index(page, idx)
    missing = await _assert_index_exists(loc, idx)
    if missing is not None:
        return missing

    if state == "check":
        await loc.first.check(timeout=_INDEX_ACTION_TIMEOUT_MS)
    else:
        await loc.first.uncheck(timeout=_INDEX_ACTION_TIMEOUT_MS)
    return ActionResult.ok()
