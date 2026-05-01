"""FastAPI Depends 함수 모음.

라우터는 모듈 글로벌을 직접 import 하지 않고 여기서 의존성을 주입받는다.
프로세스 단위 ``SqliteSessionStore`` 싱글톤도 이 모듈이 소유한다 — ``session.py``
는 도메인 정의만 담고, FastAPI 통합 글로벌은 한 곳(deps)에서 관리한다.

PR3 부터 ``get_session_store`` 는 ``lru_cache`` 로 lazy 인스턴스화한다 — 모듈 import
시점이 아니라 첫 ``Depends`` 호출 시점에 ``get_settings().db_path`` 를 평가하므로
테스트에서 ``OKDOIT_DATA_DIR`` 를 monkeypatch 한 뒤 ``cache_clear`` 하면 격리된다.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Iterator

from fastapi import Depends, HTTPException, status

from server.internal.config import ServerSettings, get_settings
from server.internal.session import Session, SqliteSessionStore
from server.internal.storage import open_connection


@lru_cache(maxsize=1)
def get_session_store() -> SqliteSessionStore:
    """프로세스 단위 단일 ``SqliteSessionStore`` 를 lazy 로 만들어 반환한다.

    첫 호출 시 ``get_settings().db_path`` 를 평가해 store 를 만든다. ``lru_cache``
    덕에 이후 호출은 같은 인스턴스를 돌려준다. 테스트에서 격리가 필요하면
    ``app.dependency_overrides[get_session_store]`` 로 주입하거나
    ``get_session_store.cache_clear()`` + ``get_settings.cache_clear()`` 조합을 쓴다.

    Returns:
        프로세스 단위 ``SqliteSessionStore`` 싱글톤.
    """
    settings = get_settings()
    return SqliteSessionStore(db_path=settings.db_path)


def get_session(
    session_id: str,
    store: SqliteSessionStore = Depends(get_session_store),
) -> Session:
    """활성 세션이 없으면 404 를 던지고, 있으면 반환한다.

    비활성(과거) 세션은 이 함수가 cover 하지 않는다 — DB 조회는 라우터가
    ``store.snapshot_of`` / ``store.screenshot_paths_for`` 로 직접 한다.

    Args:
        session_id: 경로 파라미터에서 받은 세션 식별자.
        store: 의존성 주입된 ``SqliteSessionStore``.

    Returns:
        조회된 활성 ``Session``.

    Raises:
        HTTPException: 활성 캐시에 없으면 status 404.
    """
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"세션을 찾을 수 없습니다: {session_id}",
        )
    return session


def get_db() -> Iterator[sqlite3.Connection]:
    """요청 단위로 새 SQLite connection 을 yield 하고, 끝나면 닫는다.

    FastAPI 의 ``Depends`` 에서 사용. 짧은 라이프사이클(요청당 1회 open/close)
    은 SQLite 비용이 마이크로초 단위라 무관하다. 병목이면 connection pool 도입.

    Yields:
        ``open_connection`` 으로 만든 connection (PRAGMA 적용 완료).
    """
    settings = get_settings()
    conn = open_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


__all__ = [
    "ServerSettings",
    "get_db",
    "get_session",
    "get_session_store",
    "get_settings",
]
