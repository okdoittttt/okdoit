"""``WS /sessions/{id}/events?since_seq=N`` 의 replay 동작 테스트.

PR4 의 핵심 사용자 가치(WS 재연결 시 누락 이벤트 복원)를 가드한다.
``TestClient.websocket_connect`` 로 종단 동작을 검증.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.internal.app import create_app
from server.internal.deps import get_session_store
from server.internal.events import SessionStarted, StepObserved
from server.internal.session import SqliteSessionStore
from server.internal.storage import init_db, open_connection, schema_sql_path
from server.internal.storage.repositories import EventRepository, SessionRepository


@pytest.fixture
def db_file(isolated_data_dir: Path) -> Path:
    """schema 가 적용된 임시 DB 파일."""
    db = isolated_data_dir / "okdoit.db"
    init_db(db, schema_sql_path())
    return db


def _seed_inactive_session(
    db_file: Path, session_id: str = "sid", count: int = 3
) -> None:
    """비활성 세션 1개 + events ``count`` 개를 DB 에 직접 채운다.

    sidecar 가 종료되어 활성 캐시는 비어있지만 DB 에는 세션 + 이벤트가 남아있는
    상태(=재시작 직후)를 모방한다.
    """
    conn = open_connection(db_file)
    try:
        SessionRepository(conn).insert(
            session_id, "task", headless=False, llm_provider=None, llm_model=None
        )
        repo = EventRepository(conn)
        repo.append(session_id, SessionStarted(session_id=session_id, task="task"), seq=1)
        for i in range(2, count + 1):
            repo.append(
                session_id,
                StepObserved(
                    session_id=session_id,
                    iteration=i - 1,
                    current_url=f"https://x/{i}",
                    screenshot_path=None,
                    interactive_count=0,
                ),
                seq=i,
            )
    finally:
        conn.close()


@pytest.fixture
def client(db_file: Path) -> Iterator[TestClient]:
    """``OKDOIT_DATA_DIR`` 가 격리된 상태로 sidecar TestClient 를 띄운다.

    routes/events_ws.py 가 ``Depends(get_settings)`` 와 ``Depends(get_session_store)``
    둘 다 사용하므로 둘 다 같은 DB 를 보도록 격리해야 한다. ``isolated_data_dir``
    가 환경변수 + 캐시 정리를 해주므로 ``create_app()`` 의 lifespan 도 같은 파일을
    부트스트랩한다 — 그래서 별도 override 가 필요 없다.
    """
    app = create_app()
    with TestClient(app) as c:
        yield c


def _drain_messages(ws: Any) -> list[dict[str, Any]]:
    """WS 가 close 될 때까지 모든 메시지를 모아 반환한다."""
    msgs: list[dict[str, Any]] = []
    try:
        while True:
            msgs.append(ws.receive_json())
    except (WebSocketDisconnect, Exception):  # noqa: BLE001
        pass
    return msgs


def test_replay_from_zero_returns_all_events(
    client: TestClient, db_file: Path
) -> None:
    """``since_seq=0`` 으로 연결하면 모든 이벤트가 envelope 으로 송신된다."""
    _seed_inactive_session(db_file, session_id="sid", count=3)

    with client.websocket_connect("/sessions/sid/events?since_seq=0") as ws:
        msgs = _drain_messages(ws)

    assert [m["seq"] for m in msgs] == [1, 2, 3]
    assert msgs[0]["event"]["type"] == "session.started"
    assert msgs[1]["event"]["type"] == "step.observed"


def test_replay_partial_skips_already_received(
    client: TestClient, db_file: Path
) -> None:
    """``since_seq=1`` 로 연결하면 seq 2, 3 만 받는다."""
    _seed_inactive_session(db_file, session_id="sid", count=3)

    with client.websocket_connect("/sessions/sid/events?since_seq=1") as ws:
        msgs = _drain_messages(ws)

    assert [m["seq"] for m in msgs] == [2, 3]


def test_replay_returns_nothing_when_already_caught_up(
    client: TestClient, db_file: Path
) -> None:
    """``since_seq`` 가 max 이상이면 빈 송신 + 정상 close."""
    _seed_inactive_session(db_file, session_id="sid", count=3)

    with client.websocket_connect("/sessions/sid/events?since_seq=99") as ws:
        msgs = _drain_messages(ws)

    assert msgs == []


def test_inactive_session_replay_then_close(
    client: TestClient, db_file: Path
) -> None:
    """비활성 세션도 ``since_seq=0`` 이면 DB 에서 replay 후 정상 close 된다.

    sidecar 재시작 후 사용자가 사이드바에서 과거 세션을 다시 열어보는 시나리오.
    """
    _seed_inactive_session(db_file, session_id="sid", count=2)

    with client.websocket_connect("/sessions/sid/events?since_seq=0") as ws:
        msgs = _drain_messages(ws)

    assert [m["seq"] for m in msgs] == [1, 2]


def test_unknown_session_without_since_seq_closes_4404(client: TestClient) -> None:
    """모르는 세션 + ``since_seq`` 미지정 → 4404 close 유지 (기존 동작)."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/sessions/no-such/events") as ws:
            ws.receive_text()


def test_unknown_session_with_since_seq_also_closes_4404(client: TestClient) -> None:
    """``since_seq`` 가 있어도 세션 자체가 DB 에 없으면 4404 — replay 건너뛴다.

    있지도 않은 세션의 이벤트를 요청하는 건 의미가 없으니 즉시 close 한다.
    """
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/sessions/no-such/events?since_seq=0") as ws:
            ws.receive_text()


def test_active_session_replay_then_live_with_dedup(
    client: TestClient, db_file: Path
) -> None:
    """활성 세션 + ``since_seq`` — replay 후 라이브 진입, race 시 seq 중복 skip.

    공식 시나리오:
        1. 사용자가 task 시작 (활성 세션 생성, events 1~2 가 DB 에 들어감)
        2. WS 끊김
        3. 같은 세션에 ``since_seq=0`` 으로 재연결
        4. replay 가 1~2 송신
        5. 새 publish 가 들어와 seq=3 envelope 가 큐 + DB 에 적재
        6. 라이브 단계에서 wire.seq=3 envelope 송신 (duplicate 방지)

    여기선 (5) 를 라이브 publish 로 모방한다.
    """
    import asyncio

    # 활성 store 를 직접 만들어 사용 — TestClient 의 라이프사이클이 만든 store 와는
    # 별개이므로 ``app.dependency_overrides`` 로 라우터에 주입한다.
    store = SqliteSessionStore(db_path=db_file)
    session = store.create(task="t")
    sid = session.id

    asyncio.run(session.publish(SessionStarted(session_id=sid, task="t")))
    asyncio.run(
        session.publish(
            StepObserved(
                session_id=sid,
                iteration=1,
                current_url="u",
                screenshot_path=None,
                interactive_count=0,
            )
        )
    )

    # 라이브 큐 진입 후 닫히게 하기 위한 sentinel.
    asyncio.run(session.close_stream())

    # 라우터가 우리 store 를 보도록 override.
    client.app.dependency_overrides[get_session_store] = lambda: store

    try:
        with client.websocket_connect(
            f"/sessions/{sid}/events?since_seq=0"
        ) as ws:
            msgs = _drain_messages(ws)
    finally:
        client.app.dependency_overrides.pop(get_session_store, None)

    # replay (seq 1, 2) 가 송신되고, 라이브 단계는 같은 envelope 들이 큐에 있어도
    # ``wire.seq <= last_replay_seq`` 가드로 중복 송신되지 않는다.
    assert [m["seq"] for m in msgs] == [1, 2]
