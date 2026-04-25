"""FastAPI Depends 함수 모음.

라우터는 모듈 글로벌을 직접 import 하지 않고 여기서 의존성을 주입받는다.
프로세스 단위 ``SessionStore`` 싱글톤도 이 모듈이 소유한다 — ``session.py``
는 순수 도메인 정의만 담고, FastAPI 통합 글로벌은 한 곳(deps)에서 관리한다.
테스트에서는 ``app.dependency_overrides`` 로 손쉽게 교체할 수 있다.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from server.internal.config import ServerSettings, get_settings
from server.internal.session import Session, SessionStore

# 프로세스 단위 단일 SessionStore. 라우터는 ``Depends(get_session_store)`` 로
# 받아가고, 테스트는 ``app.dependency_overrides`` 로 격리 store 를 주입한다.
_session_store: SessionStore = SessionStore()


def get_session_store() -> SessionStore:
    """프로세스 단위 단일 ``SessionStore`` 를 반환한다.

    테스트에서 격리가 필요하면 ``app.dependency_overrides[get_session_store]``
    로 새 인스턴스를 주입한다.

    Returns:
        모듈 글로벌 ``_session_store`` 싱글톤.
    """
    return _session_store


def get_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
) -> Session:
    """세션이 없으면 404 를 던지고, 있으면 반환한다.

    Args:
        session_id: 경로 파라미터에서 받은 세션 식별자.
        store: 의존성 주입된 ``SessionStore``.

    Returns:
        조회된 ``Session``.

    Raises:
        HTTPException: 해당 ``session_id`` 가 store 에 없으면 status 404 로 던진다.
    """
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"세션을 찾을 수 없습니다: {session_id}",
        )
    return session


__all__ = [
    "ServerSettings",
    "get_session",
    "get_session_store",
    "get_settings",
]
