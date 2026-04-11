import os
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


class BrowserManager:
    """Playwright 브라우저 싱글톤 관리자

    브라우저 인스턴스를 단일 객체로 유지하며 생명주기를 관리한다.
    
    Attributes:
        headless (bool): 헤드리스 모드 여부
        screenshot_dir (str): 스크린샷 저장 디렉토리 경로
    
    Example:
        >>> manager = BrowserManager(headless=False)
        >>> await manager.start()
        >>> page = await manager.get_page()
        >>> await manager.stop()
    """

    _instance: Optional["BrowserManager"] = None

    def __new__(cls, *args, **kwargs) -> "BrowserManager":
        """싱글톤 인스턴스를 반환한다.

        Returns:
            BrowserManager: 싱글톤 BrowserManager 인스턴스
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, headless: bool = True, screenshot_dir: str = ".screenshots") -> None:
        """BrowserManager를 초기화한다.

        Args:
            headless: 헤드리스 모드 여부. 기본값 True.
            screenshot_dir: 스크린샷 저장 경로. 기본값 '.screenshots'.
        """
        if hasattr(self, "_initialized"):
            return
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._initialized = True
    
    async def start(self) -> None:
        """브라우저를 실행한다.

        Playwright를 시작하고 Chromium 브라우저와 새 컨텍스트, 페이지를 생성한다.
        """
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
    
    async def stop(self) -> None:
        """브라우저를 종료한다.

        컨텍스트, 브라우저, Playwright 순으로 정리하고 싱글톤 인스턴스를 초기화한다.
        다음 태스크에서 start()를 다시 호출할 수 있도록 _instance를 None으로 리셋한다.
        """
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        BrowserManager._instance = None
    
    async def get_page(self) -> Page:
        """현재 활성 페이지를 반환한다.
        
        Returns:
            현재 활성 Playwright 페이지 객체
        
        Raises:
            RuntimeError: start()가 호출되지 않아 페이지가 없는 경우
        """
        if self._page is None:
            raise RuntimeError("Browser did not start. Plz call start() first")
        return self._page
    
    async def take_screenshot(self, filename: str) -> str:
        """스크린샷을 찍고 경로를 반환한다.

        Args:
            filename: 저장할 파일 이름

        Returns:
            저장된 스크린샷의 절대 경로
        
        Raises:
            RuntimeError: start()가 호출되지 않아 페이지가 없는 경우
        """
        os.makedirs(self.screenshot_dir, exist_ok=True)
        path = os.path.join(self.screenshot_dir, filename)
        page = await self.get_page()
        await page.screenshot(path=path)
        return path