"""``server.internal.session`` Session / SessionStore 동작 테스트."""

from __future__ import annotations

import asyncio

import pytest

from server.internal.events import SessionStarted
from server.internal.session import (
    SESSION_QUEUE_MAXSIZE,
    Session,
    SessionStatus,
    SessionStore,
)


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
    """publish 한 이벤트가 next_event 로 그대로 나와야 한다."""
    s = Session(task="t")
    evt = SessionStarted(session_id=s.id, task="t")
    await s.publish(evt)

    received = await asyncio.wait_for(s.next_event(), timeout=1.0)
    assert received is evt


@pytest.mark.asyncio
async def test_close_stream_returns_none() -> None:
    """close_stream 호출 후 next_event 는 None 을 반환해야 한다."""
    s = Session(task="t")
    await s.close_stream()
    received = await asyncio.wait_for(s.next_event(), timeout=1.0)
    assert received is None


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_event() -> None:
    """큐가 가득 차면 가장 오래된 이벤트가 폐기되고 새 이벤트가 들어가야 한다."""
    s = Session(task="t")

    # SESSION_QUEUE_MAXSIZE 가 큰 값이므로 테스트에서는 작게 다시 만든다.
    s._queue = asyncio.Queue(maxsize=2)  # noqa: SLF001 (테스트 한정 패치)

    e1 = SessionStarted(session_id=s.id, task="1")
    e2 = SessionStarted(session_id=s.id, task="2")
    e3 = SessionStarted(session_id=s.id, task="3")
    await s.publish(e1)
    await s.publish(e2)
    await s.publish(e3)  # e1 폐기, e3 enqueue

    a = await s.next_event()
    b = await s.next_event()
    assert a.task == "2"  # type: ignore[union-attr]
    assert b.task == "3"  # type: ignore[union-attr]


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


def test_store_create_get_remove() -> None:
    """SessionStore CRUD 기본 동작."""
    store = SessionStore()
    s = store.create(task="hello")
    assert store.get(s.id) is s
    assert s in store.list_all()
    store.remove(s.id)
    assert store.get(s.id) is None
