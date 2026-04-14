"""네비게이션 액션 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.actions.navigation import navigate, back, refresh, screenshot, scroll_to_element


@pytest.mark.asyncio
async def test_navigate_calls_goto():
    """navigate가 page.goto()를 올바른 인자로 호출하는지 확인한다."""
    mock_page = AsyncMock()
    action = {"type": "navigate", "value": "https://example.com"}

    await navigate(mock_page, action)

    mock_page.goto.assert_called_once_with(
        "https://example.com",
        timeout=30_000,
        wait_until="domcontentloaded",
    )


@pytest.mark.asyncio
async def test_navigate_propagates_playwright_timeout():
    """page.goto()에서 발생한 예외가 그대로 전파되는지 확인한다."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    mock_page = AsyncMock()
    mock_page.goto.side_effect = PlaywrightTimeoutError("timeout")
    action = {"type": "navigate", "value": "https://example.com"}

    with pytest.raises(PlaywrightTimeoutError):
        await navigate(mock_page, action)


@pytest.mark.asyncio
async def test_back_calls_go_back():
    """back이 page.go_back()을 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await back(mock_page, {"type": "back"})
    mock_page.go_back.assert_called_once_with(timeout=10_000)


@pytest.mark.asyncio
async def test_refresh_calls_reload():
    """refresh가 page.reload()를 올바른 인자로 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await refresh(mock_page, {"type": "refresh"})
    mock_page.reload.assert_called_once_with(timeout=30_000, wait_until="domcontentloaded")


@pytest.mark.asyncio
async def test_refresh_propagates_playwright_timeout():
    """page.reload()에서 발생한 예외가 그대로 전파되는지 확인한다."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    mock_page = AsyncMock()
    mock_page.reload.side_effect = PlaywrightTimeoutError("timeout")

    with pytest.raises(PlaywrightTimeoutError):
        await refresh(mock_page, {"type": "refresh"})


@pytest.mark.asyncio
async def test_screenshot_calls_page_screenshot(tmp_path, monkeypatch):
    """screenshot이 page.screenshot()을 호출하는지 확인한다."""
    import core.actions.navigation as nav_module
    monkeypatch.setattr(nav_module, "_SCREENSHOT_DIR", str(tmp_path))

    mock_page = AsyncMock()
    await screenshot(mock_page, {"type": "screenshot", "filename": "test.png"})

    mock_page.screenshot.assert_called_once()
    call_kwargs = mock_page.screenshot.call_args[1]
    assert call_kwargs["path"].endswith("test.png")


@pytest.mark.asyncio
async def test_screenshot_uses_timestamp_when_no_filename(tmp_path, monkeypatch):
    """filename 생략 시 타임스탬프 기반 파일명을 사용하는지 확인한다."""
    import core.actions.navigation as nav_module
    monkeypatch.setattr(nav_module, "_SCREENSHOT_DIR", str(tmp_path))

    mock_page = AsyncMock()
    await screenshot(mock_page, {"type": "screenshot"})

    mock_page.screenshot.assert_called_once()
    call_kwargs = mock_page.screenshot.call_args[1]
    assert "manual_" in call_kwargs["path"]


@pytest.mark.asyncio
async def test_scroll_to_element_calls_scroll_into_view():
    """scroll_to_element이 locator.first.scroll_into_view_if_needed()를 호출하는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.scroll_into_view_if_needed = AsyncMock()
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    await scroll_to_element(mock_page, {"type": "scroll_to_element", "value": "푸터"})

    mock_locator.first.scroll_into_view_if_needed.assert_called_once()


@pytest.mark.asyncio
async def test_scroll_to_element_raises_when_not_found():
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.scroll_into_view_if_needed = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_text = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.locator = MagicMock(return_value=mock_locator)

    with pytest.raises(RuntimeError, match="스크롤할 요소를 찾을 수 없습니다"):
        await scroll_to_element(mock_page, {"type": "scroll_to_element", "value": "없는요소"})


@pytest.mark.asyncio
async def test_back_with_count():
    """count만큼 여러 번 go_back을 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await back(mock_page, {"type": "back", "count": 3})
    assert mock_page.go_back.call_count == 3
    # 모든 호출의 timeout 인자 확인
    for call in mock_page.go_back.call_args_list:
        assert call[1]["timeout"] == 10_000
