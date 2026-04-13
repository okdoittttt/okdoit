"""네비게이션 액션 단위 테스트."""

import pytest
from unittest.mock import AsyncMock

from core.actions.navigation import navigate


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
