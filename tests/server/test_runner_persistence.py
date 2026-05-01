"""sidecar 재시작 시나리오 — 종료 후 재가동해도 ``GET /sessions`` 가 보존된다.

PR3 의 핵심 사용자 가치(머지 후 sidecar 재시작 후에도 과거 세션 조회 가능)를
가드한다. ``/run`` 1번 → store evict 로 활성 캐시 정리 → 새 ``SqliteSessionStore``
인스턴스로 같은 DB 를 다시 열어 ``GET /sessions`` 응답이 그대로 보이는지 확인.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from server.internal.events import SessionFinished, SessionStarted
from server.internal.session import SessionStatus, SqliteSessionStore
from server.internal.storage import init_db, open_connection, schema_sql_path
from server.internal.storage.repositories import EventRepository, SessionRepository


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    """schema 가 적용된 임시 DB 파일."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    return db


@pytest.mark.asyncio
async def test_session_row_survives_store_replacement(db_file: Path) -> None:
    """하나의 DB 파일을 두 store 인스턴스가 차례로 보면 같은 세션이 노출된다.

    sidecar 재시작 시나리오의 단위 테스트 등가물 — 인메모리 활성 캐시는 프로세스
    경계에서 사라지지만 DB row 는 보존되므로 새 store 가 이를 그대로 본다.
    """
    # ── 1차 store: 세션 1개 만들고 종료 ──
    store1 = SqliteSessionStore(db_path=db_file)
    session = store1.create(task="first")
    sid = session.id

    # 사용자가 종료된 세션을 보는 것처럼 status 를 FINISHED 로 갱신.
    conn = open_connection(db_file)
    try:
        SessionRepository(conn).update_status(
            sid,
            SessionStatus.FINISHED,
            iterations=2,
            result="ok",
            error=None,
            finished=True,
        )
    finally:
        conn.close()
    store1.evict(sid)  # 활성 캐시에서도 제거 — 사이드카 재시작 모방.

    # ── 2차 store: 같은 DB 를 새로 열어도 세션이 보인다 ──
    store2 = SqliteSessionStore(db_path=db_file)
    assert store2.get(sid) is None  # 활성 캐시는 비어있다.
    snap = store2.snapshot_of(sid)
    assert snap is not None
    assert snap.task == "first"
    assert snap.status == SessionStatus.FINISHED
    assert snap.result == "ok"
    assert snap.iterations == 2

    # list_all 에도 포함된다 — 사이드바 / GET /sessions 가 보는 동일 경로.
    snaps = store2.list_all()
    assert any(s.id == sid for s in snaps)


@pytest.mark.asyncio
async def test_persisted_events_match_publish_seq(db_file: Path) -> None:
    """``Session.publish`` 가 events 테이블에 seq 와 함께 차곡차곡 쌓인다.

    DB write 는 ``asyncio.to_thread`` 로 비동기 호출되지만 ``publish`` 가 그 결과를
    ``await`` 하므로, ``publish`` 가 반환되면 row 가 이미 들어가 있다.
    """
    store = SqliteSessionStore(db_path=db_file)
    session = store.create(task="t")

    await session.publish(SessionStarted(session_id=session.id, task="t"))
    await session.publish(
        SessionFinished(session_id=session.id, result="ok", iterations=1)
    )

    conn = open_connection(db_file)
    try:
        events = EventRepository(conn).list_after(session.id, since_seq=0)
    finally:
        conn.close()
    assert [e.type for e in events] == ["session.started", "session.finished"]


@pytest.mark.asyncio
async def test_publish_seq_persists_in_order(db_file: Path) -> None:
    """publish 호출 순서대로 ``events.seq`` 가 1, 2, 3 으로 적재된다."""
    store = SqliteSessionStore(db_path=db_file)
    session = store.create(task="t")

    for i in range(3):
        await session.publish(
            SessionStarted(session_id=session.id, task=f"task-{i}")
        )

    conn = open_connection(db_file)
    try:
        rows = conn.execute(
            "SELECT seq FROM events WHERE session_id=? ORDER BY seq ASC",
            (session.id,),
        ).fetchall()
    finally:
        conn.close()
    assert [r[0] for r in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_directly_published_event_via_routes_is_persisted(
    db_file: Path,
) -> None:
    """``routes/sessions.py`` 의 ``pause``/``resume`` 처럼 store 우회 publish 도 영속화된다.

    검증 에이전트 발견: seq 카운터가 runner 가 아닌 ``Session`` 자체에 있어
    어디서 publish 하든 같은 경로로 DB 에 들어가야 한다. 라우터 직접 publish 가
    누락되지 않는지 가드.
    """
    store = SqliteSessionStore(db_path=db_file)
    session = store.create(task="t")

    # routes/sessions.py 의 pause_session 이 하는 호출과 등가.
    from server.internal.events import SessionPaused

    await session.publish(SessionPaused(session_id=session.id))

    conn = open_connection(db_file)
    try:
        events = EventRepository(conn).list_after(session.id, since_seq=0)
    finally:
        conn.close()
    assert len(events) == 1
    assert events[0].type == "session.paused"
