"""``sessions`` 테이블 CRUD."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from server.internal.session_models import SessionSnapshot, SessionStatus

# 한 번에 반환할 세션 개수의 안전 상한 — store 의 LIST_LIMIT_DEFAULT 와 동일하지만,
# 중복 import 를 피하기 위해 repository 안에 별도 상수로 둔다.
_DEFAULT_LIST_LIMIT: int = 100


def _now_iso() -> str:
    """현재 UTC 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat()


class SessionRepository:
    """``sessions`` 테이블 접근자.

    sync ``sqlite3`` 를 직접 사용한다. async 호출 측은 메서드를
    ``asyncio.to_thread(...)`` 로 감싼다.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """저장소를 초기화한다.

        Args:
            conn: ``open_connection`` 으로 만든 connection. 라이프사이클은 호출 측이 관리.
        """
        self._conn = conn

    def insert(
        self,
        session_id: str,
        task: str,
        headless: bool,
        llm_provider: Optional[str],
        llm_model: Optional[str],
    ) -> None:
        """새 세션 row 를 insert 한다 (status=IDLE).

        Args:
            session_id: uuid4 문자열.
            task: 사용자 입력 태스크.
            headless: 브라우저 헤드리스 여부.
            llm_provider: 실행 시점 프로바이더 스냅샷. None 이면 NULL 저장.
            llm_model: 실행 시점 모델명 스냅샷.
        """
        now = _now_iso()
        self._conn.execute(
            """
            INSERT INTO sessions(
                id, task, status, iterations, headless,
                llm_provider, llm_model, created_at, updated_at
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                task,
                SessionStatus.IDLE.value,
                int(headless),
                llm_provider,
                llm_model,
                now,
                now,
            ),
        )

    def update_status(
        self,
        session_id: str,
        status: SessionStatus,
        iterations: int,
        result: Optional[str] = None,
        error: Optional[str] = None,
        finished: bool = False,
    ) -> None:
        """세션 상태를 갱신한다.

        Args:
            session_id: 대상 세션.
            status: 새 라이프사이클 상태.
            iterations: 최신 반복 횟수.
            result: 종료 시 결과 텍스트.
            error: 에러 종료 시 메시지.
            finished: True 이면 ``finished_at`` 도 현재 시각으로 채운다.
        """
        now = _now_iso()
        self._conn.execute(
            """
            UPDATE sessions
            SET status=?, iterations=?, result=?, error=?, updated_at=?,
                finished_at=COALESCE(?, finished_at)
            WHERE id=?
            """,
            (
                status.value,
                iterations,
                result,
                error,
                now,
                now if finished else None,
                session_id,
            ),
        )

    def cleanup_stale_active(self, message: str) -> int:
        """sidecar 시작 시 RUNNING / PAUSED 로 남은 세션을 ERRORED 로 정리한다.

        DB write 실패나 sidecar 강제 종료로 활성 상태가 남은 row 를 한 번에 처리.
        local-first 환경(단일 sidecar) 가정이라 안전하다.

        Args:
            message: ``error`` 컬럼에 채울 메시지 (예: "sidecar restart").

        Returns:
            상태가 갱신된 row 수.
        """
        now = _now_iso()
        cur = self._conn.execute(
            """
            UPDATE sessions
            SET status=?, error=?, updated_at=?,
                finished_at=COALESCE(finished_at, ?)
            WHERE status IN (?, ?)
            """,
            (
                SessionStatus.ERRORED.value,
                message,
                now,
                now,
                SessionStatus.RUNNING.value,
                SessionStatus.PAUSED.value,
            ),
        )
        return int(cur.rowcount)

    def get(self, session_id: str) -> Optional[SessionSnapshot]:
        """단일 세션 스냅샷을 조회한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            row 가 있으면 ``SessionSnapshot``, 없으면 None.
        """
        row = self._conn.execute(
            """
            SELECT id, task, status, iterations, result, error, created_at
            FROM sessions WHERE id=?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return SessionSnapshot(
            id=row["id"],
            task=row["task"],
            status=SessionStatus(row["status"]),
            iterations=row["iterations"],
            result=row["result"],
            error=row["error"],
            created_at=row["created_at"],
        )

    def list_all(self, limit: int = _DEFAULT_LIST_LIMIT) -> list[SessionSnapshot]:
        """최근 세션 ``limit`` 개를 created_at 내림차순으로 반환한다.

        Args:
            limit: 반환할 최대 개수.

        Returns:
            ``SessionSnapshot`` 리스트 (최신 먼저).
        """
        rows = self._conn.execute(
            """
            SELECT id, task, status, iterations, result, error, created_at
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            SessionSnapshot(
                id=r["id"],
                task=r["task"],
                status=SessionStatus(r["status"]),
                iterations=r["iterations"],
                result=r["result"],
                error=r["error"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
