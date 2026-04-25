import contextvars
import os
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import Stealth

_headless_default = os.environ.get("BROWSER_HEADLESS", "true").lower() != "false"


# 현재 asyncio task 에 바인딩된 활성 BrowserManager. 노드 / 액션 코드가
# ``BrowserManager.current()`` 로 가져간다. ``asyncio.create_task`` 가 부모 context
# 를 자동 copy 하므로 runner 가 한 번 ``bind()`` 하면 그 task 안의 모든 await
# 체인(observe → think → act → ...)이 같은 매니저를 본다.
_current_manager: contextvars.ContextVar[Optional["BrowserManager"]] = contextvars.ContextVar(
    "browser_manager",
    default=None,
)


class BrowserManager:
    """Playwright 브라우저 인스턴스 관리자.

    각 인스턴스는 독립된 Playwright runtime + Chromium 프로세스 + Page 를 가진다.
    멀티 세션(``server.internal``)이 동시에 작업할 때 서로 간섭하지 않도록
    인스턴스마다 완전히 격리된다.

    노드 / 액션 코드는 ``BrowserManager.current()`` 로 현재 세션의 매니저를
    가져간다. 매니저 라이프사이클은 호출 측(runner / CLI)이 ``bind()`` /
    ``unbind()`` 로 명시적으로 관리한다.

    이전(v0.2 까지)은 클래스 싱글톤이었으나 v0.3 멀티 세션 도입과 함께
    ``contextvars`` 기반 세션별 격리로 전환했다.

    Attributes:
        headless (bool): 헤드리스 모드 여부.
        screenshot_dir (str): 스크린샷 저장 디렉토리 경로.

    Example:
        >>> manager = BrowserManager(headless=False)
        >>> token = manager.bind()
        >>> try:
        ...     await manager.start()
        ...     page = await manager.get_page()
        ... finally:
        ...     await manager.stop()
        ...     BrowserManager.unbind(token)
    """

    def __init__(self, headless: bool = _headless_default, screenshot_dir: str = ".screenshots") -> None:
        """BrowserManager 를 초기화한다.

        Args:
            headless: 헤드리스 모드 여부. 기본값 환경변수 ``BROWSER_HEADLESS`` 따름.
            screenshot_dir: 스크린샷 저장 경로. 기본값 ``.screenshots``.
        """
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        # ``start()`` 가 자동 bind 한 토큰. 외부에서 명시적으로 ``bind()`` 한 경우엔
        # ``start()`` 가 추가로 bind 하지 않는다.
        self._auto_bind_token: Optional[contextvars.Token] = None

    # ── 컨텍스트 바인딩 ───────────────────────────────────────

    @classmethod
    def current(cls) -> "BrowserManager":
        """현재 asyncio task 에 바인딩된 매니저를 반환한다.

        Returns:
            ``bind()`` 로 등록된 ``BrowserManager``.

        Raises:
            RuntimeError: 현재 task 에 바인딩된 매니저가 없을 때.
        """
        m = _current_manager.get()
        if m is None:
            raise RuntimeError(
                "현재 task 에 BrowserManager 가 바인딩되지 않았습니다. "
                "runner / CLI 진입점에서 ``manager.bind()`` 를 먼저 호출하세요."
            )
        return m

    def bind(self) -> contextvars.Token:
        """이 매니저를 현재 task 의 활성 매니저로 등록한다.

        Returns:
            ``unbind`` 에 넘길 ``Token``.
        """
        return _current_manager.set(self)

    @staticmethod
    def unbind(token: contextvars.Token) -> None:
        """``bind()`` 가 돌려준 토큰으로 활성 매니저 등록을 해제한다.

        Args:
            token: ``bind()`` 가 반환한 토큰.
        """
        _current_manager.reset(token)

    # ── 라이프사이클 ───────────────────────────────────────────

    async def start(self) -> None:
        """브라우저를 실행한다.

        Playwright 를 시작하고 Chromium 브라우저 + 새 컨텍스트 + 페이지를 만든다.
        같은 인스턴스의 ``stop()`` 후 다시 호출하면 새 브라우저를 띄울 수 있다.

        외부에서 ``bind()`` 가 호출되지 않은 상태라면 자동으로 현재 task 에 bind
        해서 노드 / 액션 코드가 ``BrowserManager.current()`` 로 이 매니저를 본다.
        """
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        self._page = await self._context.new_page()
        await Stealth().apply_stealth_async(self._page)
        # 외부에서 미리 bind 하지 않았으면 자동으로 현재 task 에 등록한다.
        if _current_manager.get() is not self:
            self._auto_bind_token = self.bind()

    async def stop(self) -> None:
        """브라우저를 종료한다.

        컨텍스트, 브라우저, Playwright 순으로 정리한다. 인스턴스마다 격리되므로
        다른 매니저에는 영향 없음. ``start()`` 가 자동 bind 한 경우 unbind 도 함께 한다.
        """
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None
        if self._auto_bind_token is not None:
            try:
                BrowserManager.unbind(self._auto_bind_token)
            except (LookupError, ValueError):
                # LIFO 순서가 어긋나 reset 이 실패해도 정리 자체는 계속 진행.
                pass
            self._auto_bind_token = None

    # ── 페이지 조회 ───────────────────────────────────────────

    async def get_page(self) -> Page:
        """현재 활성 페이지를 반환한다.

        Returns:
            현재 활성 Playwright 페이지 객체.

        Raises:
            RuntimeError: ``start()`` 가 호출되지 않아 페이지가 없는 경우.
        """
        if self._page is None:
            raise RuntimeError("Browser did not start. Plz call start() first")
        return self._page

    async def take_screenshot(self, filename: str) -> str:
        """스크린샷을 찍고 경로를 반환한다.

        Args:
            filename: 저장할 파일 이름.

        Returns:
            저장된 스크린샷의 절대 경로.

        Raises:
            RuntimeError: ``start()`` 가 호출되지 않아 페이지가 없는 경우.
        """
        os.makedirs(self.screenshot_dir, exist_ok=True)
        path = os.path.join(self.screenshot_dir, filename)
        page = await self.get_page()
        await page.screenshot(path=path)
        return path
