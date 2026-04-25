import os
import pytest

from core.browser import BrowserManager


@pytest.mark.asyncio
async def test_each_instance_is_independent():
    """v0.3 부터 BrowserManager 는 더 이상 싱글톤이 아니다.

    멀티 세션이 동시에 작업할 때 서로 다른 Chromium / Page 를 가져야 한다.
    """
    manager1 = BrowserManager()
    manager2 = BrowserManager()
    assert manager1 is not manager2


@pytest.mark.asyncio
async def test_get_page_without_start_raises_error():
    """start() 없이 get_page() 호출 시 RuntimeError가 발생하는지 확인한다."""
    manager = BrowserManager()
    with pytest.raises(RuntimeError):
        await manager.get_page()


@pytest.mark.asyncio
async def test_start_and_get_page():
    """start() 후 get_page()가 정상적으로 Page를 반환하는지 확인한다."""
    manager = BrowserManager(headless=False)
    try:
        await manager.start()
        page = await manager.get_page()
        assert page is not None
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stop_clears_internal_state():
    """stop() 후 내부 핸들이 모두 None 으로 리셋되어 재사용 가능해야 한다."""
    manager = BrowserManager(headless=False)
    await manager.start()
    await manager.stop()
    assert manager._playwright is None  # noqa: SLF001 (테스트 한정 검증)
    assert manager._browser is None  # noqa: SLF001
    assert manager._context is None  # noqa: SLF001
    assert manager._page is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_two_managers_run_concurrently_with_isolated_pages():
    """두 매니저를 동시에 띄웠을 때 서로 다른 Page 가 살아 있어야 한다.

    v0.3 회귀 케이스: 싱글톤 시절엔 두 번째 ``start()`` 가 첫 번째 ``_page``
    참조를 덮어 써서 첫 세션의 작업이 잘못된 페이지로 흘러갔다.
    """
    m1 = BrowserManager(headless=False)
    m2 = BrowserManager(headless=False)
    try:
        await m1.start()
        await m2.start()
        page1 = await m1.get_page()
        page2 = await m2.get_page()
        assert page1 is not page2
    finally:
        await m1.stop()
        await m2.stop()


@pytest.mark.asyncio
async def test_take_screenshot(tmp_path):
    """스크린샷 파일이 실제로 생성되는지 확인한다."""
    manager = BrowserManager(headless=False, screenshot_dir=str(tmp_path))
    try:
        await manager.start()
        path = await manager.take_screenshot("test_step.png")
        assert os.path.exists(path)
    finally:
        await manager.stop()
