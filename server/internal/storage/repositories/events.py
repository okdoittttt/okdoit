"""``events`` 테이블 CRUD + WS replay 지원."""

from __future__ import annotations

import sqlite3

from pydantic import TypeAdapter

from server.internal.events import ServerEvent

# ``ServerEvent`` 합집합을 raw JSON 으로 역직렬화하는 단일 어댑터.
# discriminated union 이라 ``type`` 필드 기준으로 자동 판별된다.
_EVENT_ADAPTER: TypeAdapter[ServerEvent] = TypeAdapter(ServerEvent)


class EventRepository:
    """``events`` 테이블 접근자.

    ``append`` 는 ``Session.publish`` 가 모든 발행을 거치는 단일 통로 — store 의
    persist 콜백이 connection 을 새로 열고 닫으며 호출한다. ``list_after`` 는
    PR4 의 WS replay 가 사용한다.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """저장소를 초기화한다.

        Args:
            conn: ``open_connection`` 으로 만든 connection.
        """
        self._conn = conn

    def append(self, session_id: str, event: ServerEvent, seq: int) -> None:
        """이벤트 1건을 append 한다.

        Args:
            session_id: 세션 식별자.
            event: ``ServerEvent`` 합집합 중 하나. ``type`` 리터럴이 들어있다.
            seq: 세션 내 단조 증가 번호. WS replay 의 키.
        """
        payload = event.model_dump_json()
        self._conn.execute(
            """
            INSERT INTO events(session_id, type, ts, payload, seq)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, event.type, event.ts, payload, seq),
        )

    def max_seq(self, session_id: str) -> int:
        """세션의 가장 큰 seq 를 반환한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            마지막 seq, 이벤트가 없으면 0.
        """
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM events WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return int(row[0])

    def list_after(self, session_id: str, since_seq: int) -> list[ServerEvent]:
        """``seq > since_seq`` 인 이벤트들을 순서대로 반환한다 (replay 용).

        Args:
            session_id: 세션 식별자.
            since_seq: 이 값 초과의 seq 만 가져온다. 0 이면 처음부터.

        Returns:
            역직렬화된 이벤트 목록 (seq 오름차순).
        """
        rows = self._conn.execute(
            """
            SELECT payload FROM events
            WHERE session_id=? AND seq > ?
            ORDER BY seq ASC
            """,
            (session_id, since_seq),
        ).fetchall()
        return [_EVENT_ADAPTER.validate_json(r["payload"]) for r in rows]
