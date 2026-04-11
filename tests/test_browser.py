import os
import pytest
import pytest_asyncio
from core.browser import BrowserManager


@pytest_asyncio.fixture(autouse=True)
async def reset_singleton():
    """각 테스트 전후로 싱글톤 인스턴스를 초기화한다."""
    BrowserManager._instance = None
    yield
    if BrowserManager._instance is not None:
        await BrowserManager._instance.stop()


@pytest.mark.asyncio
async def test_singleton():
    """동일한 인스턴스를 반환하는지 확인한다."""
    manager1 = BrowserManager()
    manager2 = BrowserManager()
    assert manager1 is manager2


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
    await manager.start()
    page = await manager.get_page()
    assert page is not None


@pytest.mark.asyncio
async def test_stop_resets_singleton():
    """stop() 후 싱글톤 인스턴스가 None으로 리셋되는지 확인한다."""
    manager = BrowserManager(headless=False)
    await manager.start()
    await manager.stop()
    assert BrowserManager._instance is None


@pytest.mark.asyncio
async def test_take_screenshot(tmp_path):
    """스크린샷 파일이 실제로 생성되는지 확인한다."""
    manager = BrowserManager(headless=False, screenshot_dir=str(tmp_path))
    await manager.start()
    path = await manager.take_screenshot("test_step.png")
    assert os.path.exists(path)