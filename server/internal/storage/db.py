"""SQLite connection 팩토리와 초기 부트스트랩.

stdlib ``sqlite3`` 만 사용한다(추가 의존성 0). FastAPI 의 async 코드에서 호출할 때는
호출 측이 ``asyncio.to_thread(...)`` 로 감싼다 — 이 모듈은 항상 sync API 를 노출.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# WAL 모드 + 외래키 강제 + busy timeout(ms). connection 마다 PRAGMA 적용 필요.
_BUSY_TIMEOUT_MS: int = 5_000


def open_connection(db_path: Path) -> sqlite3.Connection:
    """SQLite 파일에 연결하고 표준 PRAGMA 를 적용한다.

    Args:
        db_path: SQLite 파일 절대 경로. 파일이 없으면 sqlite3 가 새로 만든다.
            부모 디렉토리는 호출 측이 보장한다.

    Returns:
        ``sqlite3.Connection`` — ``Row`` factory 가 적용돼 dict-like 접근 가능.

    Note:
        ``isolation_level=None`` 으로 autocommit 모드를 켠다. 트랜잭션은
        호출 측이 ``BEGIN`` / ``COMMIT`` 을 명시한다(``executescript`` 는 예외 —
        내부적으로 자체 트랜잭션을 연다).
        ``check_same_thread=False`` 는 ``asyncio.to_thread`` 로 다른 스레드에서
        호출할 가능성에 대비한다 — 단일 sidecar 프로세스라 동시 쓰기 충돌은 없다.
    """
    conn = sqlite3.connect(
        db_path,
        isolation_level=None,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    return conn


def init_db(db_path: Path, schema_sql_path: Path) -> None:
    """DB 파일이 없으면 만들고 초기 스키마를 적용한다.

    초기 스키마는 ``CREATE TABLE IF NOT EXISTS`` 라 idempotent. 누적 마이그레이션은
    ``migrations.apply()`` 가 책임진다.

    Args:
        db_path: SQLite 파일 절대 경로.
        schema_sql_path: 초기 ``schema.sql`` 절대 경로.

    Raises:
        FileNotFoundError: ``schema_sql_path`` 가 존재하지 않을 때 — PyInstaller
            datas 등록이 누락된 경우 첫 prod 부팅에서 즉시 발견하기 위함.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = schema_sql_path.read_text(encoding="utf-8")
    conn = open_connection(db_path)
    try:
        conn.executescript(schema_sql)
        logger.info("DB 초기 스키마 적용: %s", db_path)
    finally:
        conn.close()


def schema_sql_path() -> Path:
    """번들된 ``schema.sql`` 의 절대 경로를 반환한다.

    PyInstaller frozen 환경에서도 동작하도록 모듈 파일 기준 상대 경로로 찾는다.
    ``okdoit-agent.spec`` 의 ``datas`` 가 같은 위치에 복사한다.

    Returns:
        ``server/internal/storage/schema.sql`` 의 절대 경로.
    """
    return Path(__file__).resolve().parent / "schema.sql"
