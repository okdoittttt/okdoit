"""``DELETE /sessions/{id}`` 라우트 동작 테스트.

세 가지 사용자 가치 가드:
    - 비활성 세션 삭제 → DB row + 자식 테이블 + 디스크 스크린샷이 모두 사라진다.
    - 존재하지 않는 세션 → 404.
    - 활성 세션 삭제 → graceful stop 후 동일하게 정리된다.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from server.internal.app import create_app
from server.internal.deps import get_session_store
from server.internal.events import SessionStarted, StepObserved
from server.internal.session import SessionStatus, SqliteSessionStore
from server.internal.session_models import SessionSnapshot
from server.internal.storage import init_db, open_connection, schema_sql_path
from server.internal.storage.repositories import (
    EventRepository,
    ScreenshotRepository,
    SessionRepository,
)


@pytest.fixture
def db_file(isolated_data_dir: Path) -> Path:
    """schema 가 적용된 임시 DB 파일."""
    db = isolated_data_dir / "okdoit.db"
    init_db(db, schema_sql_path())
    return db


@pytest.fixture
def client(db_file: Path) -> Iterator[TestClient]:
    """``OKDOIT_DATA_DIR`` 가 격리된 sidecar TestClient.

    ``isolated_data_dir`` fixture 가 환경변수 + lru_cache 정리를 처리하므로
    ``create_app()`` 의 lifespan 이 같은 DB 를 부트스트랩한다.
    """
    app = create_app()
    with TestClient(app) as c:
        yield c


def _seed_session_with_data(
    db_file: Path,
    screenshot_root: Path,
    session_id: str = "sid",
) -> Path:
    """비활성 세션 + events 2건 + screenshots 1건 + 디스크 파일 1개를 세팅한다.

    Returns:
        세션의 스크린샷 디렉토리 경로 (검증에 쓴다).
    """
    conn = open_connection(db_file)
    try:
        SessionRepository(conn).insert(
            session_id, "task", headless=False, llm_provider=None, llm_model=None
        )
        events = EventRepository(conn)
        events.append(
            session_id, SessionStarted(session_id=session_id, task="task"), seq=1
        )
        events.append(
            session_id,
            StepObserved(
                session_id=session_id,
                iteration=1,
                current_url="https://x",
                screenshot_path=None,
                interactive_count=0,
            ),
            seq=2,
        )
    finally:
        conn.close()

    # 디스크 스크린샷 1개 + screenshots row 1개. _to_screenshot_url 은 절대경로 기대.
    sid_dir = screenshot_root / session_id
    sid_dir.mkdir(parents=True, exist_ok=True)
    shot_path = sid_dir / "step_1.png"
    shot_path.write_bytes(b"fake png")

    conn = open_connection(db_file)
    try:
        ScreenshotRepository(conn).append(
            session_id=session_id, path=str(shot_path), step_index=1
        )
    finally:
        conn.close()

    return sid_dir


def test_delete_inactive_session_removes_row_and_disk(
    client: TestClient, db_file: Path, isolated_data_dir: Path
) -> None:
    """비활성 세션 DELETE → 200, DB row / events / screenshots / 디스크 모두 정리."""
    screenshot_root = isolated_data_dir / "screenshots"
    sid_dir = _seed_session_with_data(db_file, screenshot_root, session_id="sid")
    assert sid_dir.exists()

    res = client.delete("/sessions/sid")
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True}

    # DB 검증 — sessions, events, screenshots 모두 비어있어야 함 (FK CASCADE)
    conn = open_connection(db_file)
    try:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM screenshots").fetchone()[0] == 0
    finally:
        conn.close()

    # 디스크 검증 — 세션 디렉토리 자체가 사라져야 함
    assert not sid_dir.exists()


def test_delete_unknown_session_returns_404(client: TestClient) -> None:
    """활성/DB 어디에도 없는 세션은 404."""
    res = client.delete("/sessions/no-such")
    assert res.status_code == 404
    assert "no-such" in res.json()["detail"]


def test_delete_idempotent_against_missing_disk_dir(
    client: TestClient, db_file: Path, isolated_data_dir: Path
) -> None:
    """DB row 는 있지만 디스크 디렉토리가 사전에 없어도 정상 처리된다.

    수동으로 디렉토리를 지운 사용자, 또는 처음부터 스크린샷이 없는 세션 케이스.
    """
    conn = open_connection(db_file)
    try:
        SessionRepository(conn).insert(
            "sid", "task", headless=False, llm_provider=None, llm_model=None
        )
    finally:
        conn.close()

    # 스크린샷 디렉토리 없음
    res = client.delete("/sessions/sid")
    assert res.status_code == 200


def test_delete_active_session_graceful_stop(
    client: TestClient, db_file: Path
) -> None:
    """활성 RUNNING 세션 DELETE → request_stop 후 terminal 도달 시점에 정리.

    runner 가 stop_event 를 감지해 status 를 STOPPED 로 sync 전이하는 동작을
    별도 task 로 모방한다 (실제 runner 의존 없이 graceful 경로만 검증).
    """
    store = SqliteSessionStore(db_path=db_file)
    session = store.create(task="long task")
    session.status = SessionStatus.RUNNING
    sid = session.id

    async def _runner_loop() -> None:
        # request_stop 이 set 한 stop_event 를 감지하면 STOPPED 로 전이.
        await session.stop_event.wait()
        await asyncio.sleep(0.05)
        session.status = SessionStatus.STOPPED

    # 라우터가 우리 store 를 쓰도록 override.
    client.app.dependency_overrides[get_session_store] = lambda: store

    async def _exercise() -> int:
        loop_task = asyncio.create_task(_runner_loop())
        try:
            # TestClient.delete 는 sync — to_thread 로 감싸 async 컨텍스트 안에서 호출.
            res = await asyncio.to_thread(client.delete, f"/sessions/{sid}")
            return res.status_code
        finally:
            await loop_task

    try:
        status_code = asyncio.run(_exercise())
    finally:
        client.app.dependency_overrides.pop(get_session_store, None)

    assert status_code == 200
    # 활성 캐시에서 evict 됐는지
    assert store.get(sid) is None
    # DB row 도 사라졌는지
    assert store.snapshot_of(sid) is None


def test_delete_active_hung_session_force_evicts_after_timeout(
    client: TestClient, db_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """runner 가 stop_event 를 무시해 status 가 종료로 안 가도 timeout 후 강제 정리.

    user 가 명시적으로 삭제를 눌렀으므로 "남기는 게 더 큰 사고" 정책을 검증한다.
    """
    # 테스트 속도를 위해 graceful timeout 을 짧게 줄인다.
    monkeypatch.setattr(
        "server.internal.routes.sessions._GRACEFUL_STOP_TIMEOUT_S", 0.2
    )

    store = SqliteSessionStore(db_path=db_file)
    session = store.create(task="hung task")
    session.status = SessionStatus.RUNNING  # 끝까지 RUNNING 으로 둠 — runner hang 을 모방
    sid = session.id

    client.app.dependency_overrides[get_session_store] = lambda: store
    try:
        res = client.delete(f"/sessions/{sid}")
    finally:
        client.app.dependency_overrides.pop(get_session_store, None)

    assert res.status_code == 200
    assert store.get(sid) is None
    assert store.snapshot_of(sid) is None
