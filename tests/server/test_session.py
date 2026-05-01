"""``server.internal.session`` Session / SqliteSessionStore 동작 테스트."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from server.internal.events import SessionStarted
from server.internal.session import (
    SESSION_QUEUE_MAXSIZE,
    Session,
    SessionStatus,
    SqliteSessionStore,
)
from server.internal.storage import init_db, schema_sql_path


@pytest.mark.asyncio
async def test_session_starts_in_idle_with_pause_set() -> None:
    """초기 상태는 IDLE, pause_event 는 set(통과) 상태여야 한다."""
    s = Session(task="t")
    assert s.status == SessionStatus.IDLE
    assert s.pause_event.is_set() is True
    assert s.stop_event.is_set() is False


@pytest.mark.asyncio
async def test_pause_then_wait_blocks_until_resume() -> None:
    """pause 후 wait_if_paused 는 resume 전까지 블로킹 되어야 한다."""
    s = Session(task="t")
    s.status = SessionStatus.RUNNING
    s.pause()
    assert s.status == SessionStatus.PAUSED

    waiter = asyncio.create_task(s.wait_if_paused())
    await asyncio.sleep(0.05)
    assert not waiter.done()

    s.resume()
    await asyncio.wait_for(waiter, timeout=1.0)
    assert s.status == SessionStatus.RUNNING


@pytest.mark.asyncio
async def test_stop_releases_pause_so_runner_can_exit() -> None:
    """PAUSED 상태에서 stop 이 들어오면 wait_if_paused 가 풀려야 한다."""
    s = Session(task="t")
    s.status = SessionStatus.RUNNING
    s.pause()

    waiter = asyncio.create_task(s.wait_if_paused())
    await asyncio.sleep(0.05)
    assert not waiter.done()

    s.request_stop()
    await asyncio.wait_for(waiter, timeout=1.0)
    assert s.stop_requested is True


@pytest.mark.asyncio
async def test_publish_and_next_event_round_trip() -> None:
    """publish 한 이벤트가 WireMessage envelope 으로 감싸져 나와야 한다.

    PR3 부터 ``next_event()`` 는 ``WireMessage`` 를 반환한다 — seq 카운터가
    매 publish 마다 1씩 증가하고 envelope.event 는 원본 객체와 동일하다.
    """
    s = Session(task="t")
    evt = SessionStarted(session_id=s.id, task="t")
    await s.publish(evt)

    received = await asyncio.wait_for(s.next_event(), timeout=1.0)
    assert received is not None
    assert received.seq == 1
    assert received.event is evt


@pytest.mark.asyncio
async def test_publish_increments_seq() -> None:
    """연속 publish 는 seq 를 1, 2, 3 ... 로 단조 증가시킨다."""
    s = Session(task="t")
    for i in range(3):
        await s.publish(SessionStarted(session_id=s.id, task=f"t{i}"))

    seqs = []
    for _ in range(3):
        wire = await asyncio.wait_for(s.next_event(), timeout=1.0)
        assert wire is not None
        seqs.append(wire.seq)
    assert seqs == [1, 2, 3]


@pytest.mark.asyncio
async def test_close_stream_returns_none() -> None:
    """close_stream 호출 후 next_event 는 None 을 반환해야 한다."""
    s = Session(task="t")
    await s.close_stream()
    received = await asyncio.wait_for(s.next_event(), timeout=1.0)
    assert received is None


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_event() -> None:
    """큐가 가득 차면 가장 오래된 envelope 가 폐기되고 새 envelope 가 들어가야 한다."""
    s = Session(task="t")

    # SESSION_QUEUE_MAXSIZE 가 큰 값이므로 테스트에서는 작게 다시 만든다.
    s._queue = asyncio.Queue(maxsize=2)  # noqa: SLF001 (테스트 한정 패치)

    e1 = SessionStarted(session_id=s.id, task="1")
    e2 = SessionStarted(session_id=s.id, task="2")
    e3 = SessionStarted(session_id=s.id, task="3")
    await s.publish(e1)
    await s.publish(e2)
    await s.publish(e3)  # e1 envelope(seq=1) 폐기, e3 envelope(seq=3) enqueue

    a = await s.next_event()
    b = await s.next_event()
    assert a is not None and b is not None
    # envelope.event.task 로 도메인 이벤트 본체에 접근.
    assert a.event.task == "2"  # type: ignore[union-attr]
    assert b.event.task == "3"  # type: ignore[union-attr]
    # seq 도 폐기되지 않고 그대로 유지(드롭은 큐 점유만 줄임).
    assert (a.seq, b.seq) == (2, 3)


def test_session_snapshot_reflects_latest_fields() -> None:
    """snapshot 에 최신 iterations / result / error 가 반영되어야 한다."""
    s = Session(task="t")
    s.status = SessionStatus.FINISHED
    s.latest_iterations = 7
    s.latest_result = "ok"
    snap = s.snapshot()
    assert snap.task == "t"
    assert snap.status == SessionStatus.FINISHED
    assert snap.iterations == 7
    assert snap.result == "ok"


def test_store_create_get_evict(tmp_path: Path) -> None:
    """SqliteSessionStore 의 활성 캐시 + DB row 동작.

    - ``create`` 후에는 활성 캐시(``get``)와 DB(``snapshot_of``) 둘 다에서 보인다.
    - ``evict`` 는 활성 캐시에서만 빼고 DB row 는 보존한다.
    """
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    store = SqliteSessionStore(db_path=db)

    s = store.create(task="hello")
    assert store.get(s.id) is s
    snap = store.snapshot_of(s.id)
    assert snap is not None
    assert snap.task == "hello"
    assert s in store.list_active()

    store.evict(s.id)
    assert store.get(s.id) is None
    # DB row 는 그대로 — 비활성 세션 조회는 여전히 가능.
    assert store.snapshot_of(s.id) is not None


def test_session_artifact_fields_default_empty() -> None:
    """v0.3 에서 추가된 아티팩트용 필드는 초기에 비어 있어야 한다."""
    s = Session(task="t")
    assert s.latest_subtasks == []
    assert s.latest_collected_data == {}
    assert s.screenshot_paths == []
