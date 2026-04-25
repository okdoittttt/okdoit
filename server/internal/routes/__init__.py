"""HTTP / WebSocket 라우터 모음.

각 도메인 라우터를 ``APIRouter`` 로 분리하고, ``register_routes(app)`` 한 곳에서
순서대로 ``include_router`` 한다. 새 라우터를 추가할 때는 이 파일만 수정한다.
"""

from __future__ import annotations

from fastapi import FastAPI

from server.internal.routes.events_ws import router as events_ws_router
from server.internal.routes.health import router as health_router
from server.internal.routes.run import router as run_router
from server.internal.routes.sessions import router as sessions_router


def register_routes(app: FastAPI) -> None:
    """주어진 FastAPI 앱에 모든 라우터를 등록한다.

    Args:
        app: 라우터를 부착할 FastAPI 인스턴스.
    """
    app.include_router(health_router)
    app.include_router(run_router)
    app.include_router(sessions_router)
    app.include_router(events_ws_router)


__all__ = ["register_routes"]
