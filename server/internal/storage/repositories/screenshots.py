"""``screenshots`` 테이블 CRUD."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional


def _now_iso() -> str:
    """현재 UTC 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat()


class ScreenshotRepository:
    """``screenshots`` 테이블 접근자.

    스크린샷 자체(파일 바이트)는 디스크에 저장하고, 이 테이블에는 경로 + 메타만
    둔다 — BLOB 저장은 백업·뷰잉 비효율 (``REFACTOR_PLAN_LOCAL_DB.md`` §2.1).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """저장소를 초기화한다.

        Args:
            conn: ``open_connection`` 으로 만든 connection.
        """
        self._conn = conn

    def append(
        self,
        session_id: str,
        path: str,
        step_index: Optional[int] = None,
    ) -> None:
        """스크린샷 메타 1건을 append 한다.

        Args:
            session_id: 세션 식별자.
            path: 파일 경로(절대 또는 ``data_dir`` 상대).
            step_index: ``iterations`` 시점 (없으면 NULL).
        """
        self._conn.execute(
            """
            INSERT INTO screenshots(session_id, path, step_index, ts)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, path, step_index, _now_iso()),
        )

    def list_for(self, session_id: str) -> list[str]:
        """세션의 스크린샷 경로들을 시간순으로 반환한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            경로 문자열 리스트 (insert 순서 = 시간순).
        """
        rows = self._conn.execute(
            "SELECT path FROM screenshots WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [r["path"] for r in rows]
