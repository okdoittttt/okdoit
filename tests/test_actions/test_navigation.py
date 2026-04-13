"""네비게이션 액션 단위 테스트."""

import pytest
from unittest.mock import AsyncMock

from core.actions.navigation import navigate, back


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
async def test_back_with_count():
    """count만큼 여러 번 go_back을 호출하는지 확인한다."""
    mock_page = AsyncMock()
    await back(mock_page, {"type": "back", "count": 3})
    assert mock_page.go_back.call_count == 3
    # 모든 호출의 timeout 인자 확인
    for call in mock_page.go_back.call_args_list:
        assert call[1]["timeout"] == 10_000
