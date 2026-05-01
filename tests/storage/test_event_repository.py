"""``EventRepository`` append + replay 동작 테스트."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from server.internal.events import SessionStarted, StepObserved
from server.internal.storage import init_db, open_connection, schema_sql_path
from server.internal.storage.repositories import EventRepository, SessionRepository


@pytest.fixture
def event_repo(tmp_path: Path) -> Iterator[EventRepository]:
    """schema + sessions row 1개가 미리 들어간 임시 DB 위의 EventRepository.

    events 테이블의 ``session_id`` 외래키 제약 때문에 부모 sessions row 가
    먼저 있어야 한다.
    """
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    SessionRepository(conn).insert(
        "sid", "task", headless=False, llm_provider=None, llm_model=None
    )
    try:
        yield EventRepository(conn)
    finally:
        conn.close()


def test_append_and_max_seq(event_repo: EventRepository) -> None:
    """append 한 다음 max_seq 가 마지막 seq 를 반환한다."""
    assert event_repo.max_seq("sid") == 0
    event_repo.append("sid", SessionStarted(session_id="sid", task="task"), seq=1)
    event_repo.append(
        "sid",
        StepObserved(
            session_id="sid",
            iteration=1,
            current_url="https://x",
            screenshot_path=None,
            interactive_count=0,
        ),
        seq=2,
    )
    assert event_repo.max_seq("sid") == 2


def test_max_seq_is_per_session(event_repo: EventRepository) -> None:
    """다른 세션의 seq 는 영향을 주지 않는다."""
    event_repo.append("sid", SessionStarted(session_id="sid", task="task"), seq=5)
    assert event_repo.max_seq("sid") == 5
    assert event_repo.max_seq("other") == 0


def test_list_after_returns_events_in_seq_order(event_repo: EventRepository) -> None:
    """list_after 는 ``seq > since_seq`` 인 이벤트만 오름차순으로 반환한다."""
    e1 = SessionStarted(session_id="sid", task="task")
    e2 = StepObserved(
        session_id="sid",
        iteration=1,
        current_url="u1",
        screenshot_path=None,
        interactive_count=0,
    )
    e3 = StepObserved(
        session_id="sid",
        iteration=2,
        current_url="u2",
        screenshot_path=None,
        interactive_count=0,
    )
    event_repo.append("sid", e1, seq=1)
    event_repo.append("sid", e2, seq=2)
    event_repo.append("sid", e3, seq=3)

    full = event_repo.list_after("sid", since_seq=0)
    assert [e.type for e in full] == ["session.started", "step.observed", "step.observed"]

    partial = event_repo.list_after("sid", since_seq=1)
    assert [e.type for e in partial] == ["step.observed", "step.observed"]

    nothing = event_repo.list_after("sid", since_seq=99)
    assert nothing == []


def test_list_after_roundtrip_preserves_payload(event_repo: EventRepository) -> None:
    """append → list_after 한 이벤트가 원본 필드를 그대로 들고 돌아온다."""
    original = StepObserved(
        session_id="sid",
        iteration=7,
        current_url="https://example.com/page",
        screenshot_path="/tmp/step_7.png",
        interactive_count=12,
    )
    event_repo.append("sid", original, seq=42)
    [restored] = event_repo.list_after("sid", since_seq=0)
    assert restored.type == "step.observed"
    assert restored.iteration == 7  # type: ignore[union-attr]
    assert restored.current_url == "https://example.com/page"  # type: ignore[union-attr]
    assert restored.screenshot_path == "/tmp/step_7.png"  # type: ignore[union-attr]
    assert restored.interactive_count == 12  # type: ignore[union-attr]
