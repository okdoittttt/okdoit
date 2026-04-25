"""HTTP / WebSocket 라우터 통합 테스트.

라우터별 단위 모듈은 ``server.internal.routes.*`` 에 분리돼 있고, 여기서는 실제
``create_app()`` 으로 만든 인스턴스에 ``TestClient`` 를 붙여 종단 동작을 검증한다.
실제 ``AgentRunner.run`` 은 LLM/Playwright 를 부르므로 모킹한다.
"""

from __future__ import annotations

import asyncio
from typing import Any, Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.internal.app import create_app
from server.internal.deps import get_session_store
from server.internal.events import SessionFinished, SessionStarted
from server.internal.session import SessionStatus, SessionStore


@pytest.fixture
def store() -> SessionStore:
    """테스트용 격리된 SessionStore."""
    return SessionStore()


@pytest.fixture
def client(store: SessionStore) -> Iterator[TestClient]:
    """``get_session_store`` 의존성을 격리 store 로 override 한 TestClient."""
    app = create_app()
    app.dependency_overrides[get_session_store] = lambda: store
    with TestClient(app) as c:
        yield c


# ── REST ────────────────────────────────────────────────────────


def test_health_returns_ok(client: TestClient) -> None:
    """``GET /health`` 는 ``status: ok`` 와 ``protocol_version`` 을 돌려준다."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "protocol_version" in body


def test_run_creates_session_and_returns_id(
    client: TestClient, store: SessionStore
) -> None:
    """``POST /run`` 은 세션을 만들고 ``session_id`` 를 돌려준다.

    runner 의 실제 실행은 모킹해서 즉시 종료시킨다.
    """

    async def _noop(self: Any) -> None:
        await self.session.publish(SessionStarted(session_id=self.session.id, task=self.session.task))
        await self.session.publish(
            SessionFinished(session_id=self.session.id, result="ok", iterations=0)
        )
        self.session.status = SessionStatus.FINISHED
        await self.session.close_stream()

    with patch("server.internal.routes.run.AgentRunner.run", new=_noop):
        resp = client.post("/run", json={"task": "hello", "headless": True})

    assert resp.status_code == 201
    sid = resp.json()["session_id"]
    assert store.get(sid) is not None


def test_run_rejects_empty_task(client: TestClient) -> None:
    """빈 task 는 422 로 거절돼야 한다."""
    resp = client.post("/run", json={"task": ""})
    assert resp.status_code == 422


def test_get_session_returns_snapshot(client: TestClient, store: SessionStore) -> None:
    """``GET /sessions/{id}`` 는 SessionSnapshot 을 돌려준다."""
    s = store.create(task="t")
    s.status = SessionStatus.RUNNING
    resp = client.get(f"/sessions/{s.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == s.id
    assert body["task"] == "t"
    assert body["status"] == "running"


def test_get_unknown_session_returns_404(client: TestClient) -> None:
    """존재하지 않는 세션은 404."""
    resp = client.get("/sessions/no-such-id")
    assert resp.status_code == 404


def test_pause_resume_flow_changes_status(
    client: TestClient, store: SessionStore
) -> None:
    """RUNNING → pause → PAUSED → resume → RUNNING 전이가 라우터 호출로 일어난다."""
    s = store.create(task="t")
    s.status = SessionStatus.RUNNING

    resp = client.post(f"/sessions/{s.id}/pause")
    assert resp.status_code == 200
    assert s.status == SessionStatus.PAUSED

    resp = client.post(f"/sessions/{s.id}/resume")
    assert resp.status_code == 200
    assert s.status == SessionStatus.RUNNING


def test_pause_finished_session_returns_409(
    client: TestClient, store: SessionStore
) -> None:
    """이미 종료된 세션은 pause 불가능."""
    s = store.create(task="t")
    s.status = SessionStatus.FINISHED
    resp = client.post(f"/sessions/{s.id}/pause")
    assert resp.status_code == 409


def test_stop_sets_stop_event(client: TestClient, store: SessionStore) -> None:
    """``stop`` 라우터는 stop_event 를 set 한다."""
    s = store.create(task="t")
    s.status = SessionStatus.RUNNING
    resp = client.post(f"/sessions/{s.id}/stop")
    assert resp.status_code == 200
    assert s.stop_requested is True


def test_list_sessions_returns_all(client: TestClient, store: SessionStore) -> None:
    """``GET /sessions`` 는 모든 스냅샷 리스트를 돌려준다."""
    s1 = store.create(task="a")
    s2 = store.create(task="b")
    resp = client.get("/sessions")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert {s1.id, s2.id} <= ids


# ── WebSocket ───────────────────────────────────────────────────


def test_websocket_streams_events_until_close(
    client: TestClient, store: SessionStore
) -> None:
    """publish 한 이벤트가 WS 로 흘러나오고 close_stream 후 종료된다."""
    session = store.create(task="t")

    async def _fill() -> None:
        await session.publish(SessionStarted(session_id=session.id, task="t"))
        await session.publish(
            SessionFinished(session_id=session.id, result="ok", iterations=1)
        )
        await session.close_stream()

    asyncio.run(_fill())

    with client.websocket_connect(f"/sessions/{session.id}/events") as ws:
        first = ws.receive_json()
        second = ws.receive_json()
        assert first["type"] == "session.started"
        assert second["type"] == "session.finished"


def test_websocket_unknown_session_closes(client: TestClient) -> None:
    """존재하지 않는 세션의 WS 는 즉시 닫혀야 한다."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/sessions/no-such/events") as ws:
            ws.receive_text()
