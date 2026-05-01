"""``SessionRepository`` CRUD + cleanup_stale_active 동작 테스트."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from server.internal.session_models import SessionStatus
from server.internal.storage import init_db, open_connection, schema_sql_path
from server.internal.storage.repositories import SessionRepository


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[SessionRepository]:
    """schema 가 적용된 임시 DB 위에 새 ``SessionRepository`` connection 을 yield."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    try:
        yield SessionRepository(conn)
    finally:
        conn.close()


def test_insert_and_get(repo: SessionRepository) -> None:
    """insert 후 get 이 같은 데이터를 IDLE 상태로 돌려준다."""
    repo.insert(
        "sid-1",
        "task-A",
        headless=True,
        llm_provider="anthropic",
        llm_model="claude",
    )
    snap = repo.get("sid-1")
    assert snap is not None
    assert snap.id == "sid-1"
    assert snap.task == "task-A"
    assert snap.status == SessionStatus.IDLE
    assert snap.iterations == 0
    assert snap.result is None
    assert snap.error is None


def test_get_returns_none_for_missing(repo: SessionRepository) -> None:
    """없는 세션 조회는 None."""
    assert repo.get("no-such") is None


def test_update_status_transitions(repo: SessionRepository) -> None:
    """update_status 가 status / iterations / result / finished_at 을 갱신한다."""
    repo.insert("sid-1", "task", headless=True, llm_provider=None, llm_model=None)
    repo.update_status("sid-1", SessionStatus.RUNNING, iterations=3)

    snap = repo.get("sid-1")
    assert snap is not None
    assert snap.status == SessionStatus.RUNNING
    assert snap.iterations == 3

    repo.update_status(
        "sid-1", SessionStatus.FINISHED, iterations=7, result="done", finished=True
    )
    snap = repo.get("sid-1")
    assert snap is not None
    assert snap.status == SessionStatus.FINISHED
    assert snap.iterations == 7
    assert snap.result == "done"


def test_list_all_orders_by_recent_first(repo: SessionRepository) -> None:
    """list_all 은 created_at 내림차순(최신 먼저)이다."""
    repo.insert("sid-1", "first", headless=True, llm_provider=None, llm_model=None)
    repo.insert("sid-2", "second", headless=True, llm_provider=None, llm_model=None)
    ids = [s.id for s in repo.list_all()]
    assert ids[0] == "sid-2"
    assert ids[1] == "sid-1"


def test_list_all_respects_limit(repo: SessionRepository) -> None:
    """limit 가 초과 row 를 잘라낸다."""
    for i in range(5):
        repo.insert(f"sid-{i}", "t", headless=True, llm_provider=None, llm_model=None)
    assert len(repo.list_all(limit=3)) == 3


def test_cleanup_stale_active_updates_running_and_paused(
    repo: SessionRepository,
) -> None:
    """RUNNING / PAUSED 두 row 가 한 번에 ERRORED 로 정리된다."""
    repo.insert("running", "t", headless=True, llm_provider=None, llm_model=None)
    repo.insert("paused", "t", headless=True, llm_provider=None, llm_model=None)
    repo.insert("done", "t", headless=True, llm_provider=None, llm_model=None)
    repo.update_status("running", SessionStatus.RUNNING, iterations=1)
    repo.update_status("paused", SessionStatus.PAUSED, iterations=1)
    repo.update_status(
        "done", SessionStatus.FINISHED, iterations=1, result="ok", finished=True
    )

    cleaned = repo.cleanup_stale_active("sidecar restart")
    assert cleaned == 2

    assert repo.get("running").status == SessionStatus.ERRORED  # type: ignore[union-attr]
    assert repo.get("paused").status == SessionStatus.ERRORED  # type: ignore[union-attr]
    # FINISHED 는 건드리지 않는다.
    assert repo.get("done").status == SessionStatus.FINISHED  # type: ignore[union-attr]


def test_cleanup_stale_active_returns_zero_when_nothing_to_clean(
    repo: SessionRepository,
) -> None:
    """RUNNING / PAUSED row 가 없으면 0을 반환한다."""
    repo.insert("done", "t", headless=True, llm_provider=None, llm_model=None)
    repo.update_status(
        "done", SessionStatus.FINISHED, iterations=0, result="ok", finished=True
    )
    assert repo.cleanup_stale_active("sidecar restart") == 0
