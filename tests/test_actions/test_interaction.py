"""상호작용 액션 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.actions.navigation import scroll
from core.actions.interaction import wait, click, type_text, press


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
    mock_page.get_by_text.return_value = mock_locator
    mock_page.get_by_role.return_value = mock_locator
    mock_page.locator.return_value = mock_locator

    with pytest.raises(RuntimeError, match="클릭할 요소를 찾을 수 없습니다"):
        await click(mock_page, {"type": "click", "value": "없는버튼"})


@pytest.mark.asyncio
async def test_type_raises_when_all_locators_fail():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.clear = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_placeholder.return_value = mock_locator
    mock_page.get_by_label.return_value = mock_locator
    mock_page.get_by_role.return_value = mock_locator
    mock_page.locator.return_value = mock_locator

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
    mock_page.get_by_text.return_value = mock_locator
    mock_page.get_by_role.return_value = mock_locator
    mock_page.locator.return_value = mock_locator

    with pytest.raises(RuntimeError, match="키 입력할 요소를 찾을 수 없습니다"):
        await press(mock_page, {"type": "press", "value": "Enter", "target": "없는요소"})
