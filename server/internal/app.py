"""FastAPI 앱 팩토리.

``main.py`` 는 uvicorn 진입점만 책임지고, 실제 앱 구성은 여기서 한다.
``create_app()`` 은 라이프사이클 / 라우터 등록 / 미들웨어 부착을 캡슐화한다.

uvicorn import string 은 ``server.internal.app:app`` 으로 통일한다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.internal.config import get_settings
from server.internal.deps import get_session_store
from server.internal.routes import register_routes

logger = logging.getLogger(__name__)

# 스크린샷 디렉토리 (``core.browser.BrowserManager.screenshot_dir`` 의 기본값과 동일).
# 절대 경로로 resolve 한 결과를 ``StaticFiles`` 에 전달한다.
SCREENSHOT_DIR_NAME: str = ".screenshots"
SCREENSHOT_MOUNT_PATH: str = "/static/screenshots"


def _ensure_screenshot_dir() -> Path:
    """스크린샷 디렉토리가 없으면 만들고 절대 경로를 반환한다.

    Returns:
        ``.screenshots`` 의 절대 경로(``Path``).
    """
    screenshots = Path(SCREENSHOT_DIR_NAME).resolve()
    screenshots.mkdir(parents=True, exist_ok=True)
    return screenshots


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """앱 라이프사이클 훅. 환경변수 로딩과 종료 정리를 담당한다.

    Args:
        app: FastAPI 인스턴스(인자로 받지만 현재 사용하지 않음).
    """
    load_dotenv()
    logger.info("sidecar 시작")
    try:
        yield
    finally:
        logger.info("sidecar 종료 — 잔여 세션 정리")
        for session in get_session_store().list_all():
            session.request_stop()


def create_app() -> FastAPI:
    """FastAPI 앱을 만들어 반환한다.

    테스트에서 격리된 인스턴스를 만들 때도 같은 함수를 호출하면 된다.

    Returns:
        라우터가 모두 부착된 ``FastAPI`` 인스턴스.
    """
    settings = get_settings()
    app = FastAPI(
        title="okdoit-agent-sidecar",
        version=settings.protocol_version,
        lifespan=_lifespan,
    )
    # CORS — Electron renderer 의 origin 이 환경마다 다르다:
    #   dev: http://localhost:5173 (Vite dev 서버)
    #   prod: file:// 또는 app://  (custom protocol)
    # sidecar 는 ``127.0.0.1`` only 바인딩이라 외부 origin 자체가 닿지 못한다.
    # 인증 정보(쿠키 등) 도 받지 않으므로 와일드카드 허용해도 안전.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app)
    # 스크린샷 정적 라우트 — 클라이언트가 ``<img src>`` 로 sidecar 가 보유한 PNG 를
    # 직접 띄울 수 있게 한다. 경로 매핑은 ``routes/sessions.py`` 의
    # ``SCREENSHOT_URL_PREFIX`` 와 동기화한다.
    screenshots_dir = _ensure_screenshot_dir()
    app.mount(
        SCREENSHOT_MOUNT_PATH,
        StaticFiles(directory=str(screenshots_dir)),
        name="screenshots",
    )
    return app


app: FastAPI = create_app()
"""모듈 import 시점에 만들어지는 기본 앱. uvicorn 의 import string 대상."""
