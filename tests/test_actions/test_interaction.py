"""상호작용 액션 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.actions.interaction import (
    check,
    click,
    drag_and_drop,
    execute_js,
    extract,
    hover,
    press,
    type_text,
    wait,
    wait_for_element,
)
from core.actions.navigation import scroll
from core.actions.result import ActionErrorCode, ActionResult


@pytest.mark.asyncio
async def test_scroll_down():
    """scroll down이 올바른 양수 delta로 evaluate를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await scroll(mock_page, {"type": "scroll", "value": "down"})
    mock_page.evaluate.assert_called_once_with("window.scrollBy(0, 500)")


@pytest.mark.asyncio
async def test_scroll_up():
    """scroll up이 올바른 음수 delta로 evaluate를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await scroll(mock_page, {"type": "scroll", "value": "up"})
    mock_page.evaluate.assert_called_once_with("window.scrollBy(0, -500)")


@pytest.mark.asyncio
async def test_wait_clamps_to_max():
    """wait가 _MAX_WAIT_SECONDS를 초과하는 값을 10초로 클램핑하는지 확인한다."""
    mock_page = AsyncMock()
    await wait(mock_page, {"type": "wait", "value": 999})
    mock_page.wait_for_timeout.assert_called_once_with(10.0 * 1_000)


@pytest.mark.asyncio
async def test_wait_normal_value():
    """wait가 정상 범위 내 값을 그대로 사용하는지 확인한다."""
    mock_page = AsyncMock()
    await wait(mock_page, {"type": "wait", "value": 2.5})
    mock_page.wait_for_timeout.assert_called_once_with(2.5 * 1_000)


@pytest.mark.asyncio
async def test_click_raises_when_all_locators_fail():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.click = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="클릭할 요소를 찾을 수 없습니다"):
        await click(mock_page, {"type": "click", "value": "없는버튼"})


@pytest.mark.asyncio
async def test_type_raises_when_all_locators_fail():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.clear = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_placeholder = MagicMock(return_value=mock_locator)
    mock_page.get_by_label = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="입력 필드를 찾을 수 없습니다"):
        await type_text(mock_page, {"type": "type", "target": "없는필드", "value": "텍스트"})


@pytest.mark.asyncio
async def test_press_without_target():
    """target 없이 press하면 page.keyboard.press()를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await press(mock_page, {"type": "press", "value": "Enter"})
    mock_page.keyboard.press.assert_called_once_with("Enter")


@pytest.mark.asyncio
async def test_press_raises_when_target_not_found():
    """target의 모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.press = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="키 입력할 요소를 찾을 수 없습니다"):
        await press(mock_page, {"type": "press", "value": "Enter", "target": "없는요소"})


@pytest.mark.asyncio
async def test_hover_calls_hover_on_locator():
    """hover가 locator.first.hover()를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.hover = AsyncMock()
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    await hover(mock_page, {"type": "hover", "value": "메뉴"})

    mock_locator.first.hover.assert_called_once()


@pytest.mark.asyncio
async def test_hover_raises_when_all_locators_fail():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.hover = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="호버할 요소를 찾을 수 없습니다"):
        await hover(mock_page, {"type": "hover", "value": "없는요소"})


@pytest.mark.asyncio
async def test_wait_for_element_calls_wait_for_visible():
    """wait_for_element가 locator.first.wait_for(state='visible')를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.wait_for = AsyncMock()
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    await wait_for_element(mock_page, {"type": "wait_for_element", "value": "로딩완료"})

    mock_locator.first.wait_for.assert_called_once_with(
        state="visible", timeout=15_000
    )


@pytest.mark.asyncio
async def test_wait_for_element_clamps_timeout_to_max():
    """timeout이 30초를 초과하면 30초로 클램핑하는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.wait_for = AsyncMock()
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    await wait_for_element(mock_page, {"type": "wait_for_element", "value": "요소", "timeout": 999})

    mock_locator.first.wait_for.assert_called_once_with(
        state="visible", timeout=30_000
    )


@pytest.mark.asyncio
async def test_wait_for_element_raises_when_not_found():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("timeout"))
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="요소가 나타나지 않습니다"):
        await wait_for_element(mock_page, {"type": "wait_for_element", "value": "없는요소"})


@pytest.mark.asyncio
async def test_check_calls_check_by_default():
    """state 생략 시 locator.first.check()를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.check = AsyncMock()
    mock_page.get_by_label = MagicMock(return_value=mock_locator)
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    await check(mock_page, {"type": "check", "value": "약관 동의"})

    mock_locator.first.check.assert_called_once()


@pytest.mark.asyncio
async def test_check_calls_uncheck_when_state_is_uncheck():
    """state가 'uncheck'이면 locator.first.uncheck()를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.uncheck = AsyncMock()
    mock_page.get_by_label = MagicMock(return_value=mock_locator)
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    await check(mock_page, {"type": "check", "value": "뉴스레터", "state": "uncheck"})

    mock_locator.first.uncheck.assert_called_once()


@pytest.mark.asyncio
async def test_check_returns_invalid_argument_on_invalid_state():
    """state가 'check'/'uncheck'가 아니면 ActionResult.fail(INVALID_ARGUMENT)을 반환한다."""
    mock_page = AsyncMock()

    result = await check(mock_page, {"type": "check", "value": "항목", "state": "toggle"})

    assert isinstance(result, ActionResult)
    assert result.success is False
    assert result.error_code == ActionErrorCode.INVALID_ARGUMENT
    assert "'toggle'" in (result.error_message or "")


@pytest.mark.asyncio
async def test_check_raises_when_all_locators_fail():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.check = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_label = MagicMock(return_value=mock_locator)
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="체크박스/라디오를 찾을 수 없습니다"):
        await check(mock_page, {"type": "check", "value": "없는항목"})


@pytest.mark.asyncio
async def test_extract_returns_text_via_css_selector():
    """CSS 선택자로 요소 텍스트를 추출해서 ActionResult.ok(extracted=...)로 반환한다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="추출된 텍스트")

    result = await extract(mock_page, {"type": "extract", "value": "h1"})

    assert result.success is True
    assert result.extracted == "추출된 텍스트"


@pytest.mark.asyncio
async def test_extract_falls_back_to_get_by_text():
    """evaluate가 None을 반환하면 get_by_text로 폴백한다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_locator = MagicMock()
    mock_locator.first.inner_text = AsyncMock(return_value="텍스트 기반 추출")
    mock_page.get_by_text = MagicMock(return_value=mock_locator)

    result = await extract(mock_page, {"type": "extract", "value": "제목"})

    assert result.success is True
    assert result.extracted == "텍스트 기반 추출"


@pytest.mark.asyncio
async def test_extract_raises_when_nothing_found():
    """모든 방법이 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_locator = MagicMock()
    mock_locator.first.inner_text = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_text = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="extract 실패"):
        await extract(mock_page, {"type": "extract", "value": "없는요소"})


@pytest.mark.asyncio
async def test_execute_js_returns_result():
    """JS 실행 결과를 ActionResult.ok(extracted=str)로 반환한다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="https://example.com")

    result = await execute_js(mock_page, {"type": "execute_js", "value": "return location.href"})

    assert result.success is True
    assert result.extracted == "https://example.com"
    mock_page.evaluate.assert_called_once_with("return location.href")


@pytest.mark.asyncio
async def test_execute_js_returns_empty_string_when_none():
    """JS 결과가 None이면 extracted가 빈 문자열이다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=None)

    result = await execute_js(mock_page, {"type": "execute_js", "value": "console.log('hi')"})

    assert result.success is True
    assert result.extracted == ""


@pytest.mark.asyncio
async def test_execute_js_raises_on_error():
    """JS 실행 오류 시 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(side_effect=Exception("SyntaxError"))

    with pytest.raises(RuntimeError, match="JS 실행 실패"):
        await execute_js(mock_page, {"type": "execute_js", "value": "!!invalid js!!"})


@pytest.mark.asyncio
async def test_drag_and_drop_uses_drag_to():
    """source와 target을 get_by_text로 찾아 drag_to를 호출하는지 확인한다."""
    mock_page = AsyncMock()

    source_locator = MagicMock()
    source_locator.first.drag_to = AsyncMock()
    target_locator = MagicMock()

    mock_page.get_by_text = MagicMock(side_effect=[source_locator, target_locator])

    await drag_and_drop(mock_page, {"type": "drag_and_drop", "source": "아이템A", "target": "영역B"})

    source_locator.first.drag_to.assert_called_once()


@pytest.mark.asyncio
async def test_drag_and_drop_falls_back_to_page_drag_and_drop():
    """drag_to가 실패하면 page.drag_and_drop으로 폴백하는지 확인한다."""
    mock_page = AsyncMock()

    source_locator = MagicMock()
    source_locator.first.drag_to = AsyncMock(side_effect=Exception("failed"))
    mock_page.get_by_text = MagicMock(return_value=source_locator)
    mock_page.drag_and_drop = AsyncMock()

    await drag_and_drop(mock_page, {"type": "drag_and_drop", "source": ".item", "target": ".zone"})

    mock_page.drag_and_drop.assert_called_once_with(".item", ".zone", timeout=10_000)
