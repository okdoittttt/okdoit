"""FastAPI 앱 팩토리.

``main.py`` 는 uvicorn 진입점만 책임지고, 실제 앱 구성은 여기서 한다.
``create_app()`` 은 라이프사이클 / 라우터 등록 / 미들웨어 부착을 캡슐화한다.

uvicorn import string 은 ``server.internal.app:app`` 으로 통일한다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from server.internal.config import get_settings
from server.internal.deps import get_session_store
from server.internal.routes import register_routes

logger = logging.getLogger(__name__)


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
    register_routes(app)
    return app


app: FastAPI = create_app()
"""모듈 import 시점에 만들어지는 기본 앱. uvicorn 의 import string 대상."""
