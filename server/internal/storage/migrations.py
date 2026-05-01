"""``PRAGMA user_version`` 기반 단순 마이그레이터.

v1 출시 시점엔 마이그레이션이 0개 또는 1개라 alembic 도입은 과투자.
누적 변경이 3개 이상 쌓이면 alembic 으로 이관(``REFACTOR_PLAN_LOCAL_DB.md`` 참고).

각 마이그레이션은 ``(target_version, description, apply_fn)`` 튜플로 등록한다.
``apply()`` 가 현재 ``user_version`` 보다 큰 항목을 순서대로 단일 트랜잭션 내에서
적용하고 ``user_version`` 을 갱신한다 — 부분 실패 시 ROLLBACK.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]
"""``(target_version, 사람이 읽을 설명, 적용 함수)``."""

MIGRATIONS: list[Migration] = []
"""v1 시점엔 비어 있다. 새 마이그레이션은 끝에 append 하고 target_version 을 +1."""


def current_version(conn: sqlite3.Connection) -> int:
    """현재 DB 의 ``user_version`` 을 반환한다.

    Args:
        conn: ``open_connection`` 으로 만든 connection.

    Returns:
        정수 ``user_version`` (초기값 0).
    """
    cur = conn.execute("PRAGMA user_version")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def apply(conn: sqlite3.Connection) -> None:
    """등록된 마이그레이션을 순서대로 적용한다.

    각 마이그레이션은 ``BEGIN ... COMMIT`` 트랜잭션 안에서 실행되고,
    완료 후 ``user_version`` 을 갱신한다. 실패 시 ROLLBACK 후 예외를 다시 던진다.

    Args:
        conn: ``open_connection`` 으로 만든 connection.

    Raises:
        Exception: apply 함수가 던진 예외를 그대로 전파(상위에서 부팅 중단 처리).
    """
    version = current_version(conn)
    for target, description, fn in MIGRATIONS:
        if target <= version:
            continue
        logger.info("마이그레이션 v%d 적용: %s", target, description)
        try:
            conn.execute("BEGIN")
            fn(conn)
            conn.execute(f"PRAGMA user_version={target}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
