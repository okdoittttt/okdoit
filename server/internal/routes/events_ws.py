"""``WS /sessions/{id}/events`` — 세션 이벤트 스트림 + replay."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.internal.config import ServerSettings, get_settings
from server.internal.deps import get_session_store
from server.internal.session import SqliteSessionStore
from server.internal.storage import open_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

# 세션 미존재 시 close 코드. RFC 6455 의 4xxx 대역(애플리케이션 정의)을 사용.
WS_SESSION_NOT_FOUND_CODE: int = 4404


@router.websocket("/sessions/{session_id}/events")
async def session_events(
    websocket: WebSocket,
    session_id: str,
    since_seq: Optional[int] = None,
    store: SqliteSessionStore = Depends(get_session_store),
    settings: ServerSettings = Depends(get_settings),
) -> None:
    """세션 이벤트 스트림. 재연결 시 ``?since_seq=N`` 으로 누락분 복원.

    동작 시나리오:
        1) **모르는 세션**: 활성 캐시도 없고 DB row 도 없으면 4404 close.
        2) **활성 세션, since_seq 미지정**: 라이브 큐만 흘려보낸다 (PR3 동작 유지).
        3) **활성 세션, since_seq 지정**: DB 에서 ``seq > since_seq`` 인 envelope 들을
           먼저 송신한 뒤 라이브 큐로 진입. race 방지를 위해 라이브 단계에서
           ``wire.seq <= last_replay_seq`` 인 envelope 은 skip.
        4) **비활성 세션**: DB replay 만 하고 정상 close. 클라이언트는 onclose
           에서 lastSeq 를 비우고 재연결을 시도하지 않는다.

    종료 조건:
        - runner 가 ``session.close_stream()`` 호출 → ``next_event()`` None.
        - 클라이언트 disconnect → ``WebSocketDisconnect``.
        - 비활성 세션 + replay 만: replay 종료 후 finally 의 close.

    Args:
        websocket: 연결.
        session_id: 경로 파라미터.
        since_seq: 이 값 초과의 seq 만 replay. 0 이면 처음부터, None 이면 replay 없음.
        store: SqliteSessionStore.
        settings: replay SQL 에 쓸 ``db_path`` 결정.
    """
    active = store.get(session_id)
    if active is None and store.snapshot_of(session_id) is None:
        await websocket.close(code=WS_SESSION_NOT_FOUND_CODE, reason="session not found")
        return

    await websocket.accept()
    logger.info(
        "WS 연결: session_id=%s active=%s since_seq=%s",
        session_id,
        active is not None,
        since_seq,
    )

    last_replay_seq = 0
    try:
        # 1) Replay 단계 — DB 에서 누락분 송신.
        if since_seq is not None:
            last_replay_seq = await _replay(
                websocket, session_id, since_seq, settings.db_path
            )

        # 2) 비활성 세션이면 replay 만 하고 정상 종료.
        if active is None:
            return

        # 3) 라이브 단계.
        while True:
            wire = await active.next_event()
            if wire is None:
                break
            # replay 직후 큐에 같은 envelope 가 남아있을 수 있다 (publish 시
            # DB / 큐 둘 다 채우는 사이의 race). 이미 보낸 seq 이하는 skip.
            if wire.seq <= last_replay_seq:
                continue
            await websocket.send_text(wire.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WS disconnect: session_id=%s", session_id)
    except Exception:  # noqa: BLE001
        logger.exception("WS 핸들러 예외: session_id=%s", session_id)
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


async def _replay(
    websocket: WebSocket,
    session_id: str,
    since_seq: int,
    db_path: Path,
) -> int:
    """DB 에서 ``seq > since_seq`` 인 events 를 envelope 으로 감싸 송신한다.

    Pydantic 역직렬화 비용을 피하기 위해 raw payload JSON 을 그대로 흘린다 —
    payload 컬럼이 이미 ``ServerEvent.model_dump_json()`` 결과이므로
    ``WireMessage`` envelope 만 문자열 조립으로 감싼다.

    Args:
        websocket: 송신 채널.
        session_id: 세션 식별자.
        since_seq: 이 값 초과의 seq 만 가져온다. 0 이면 처음부터.
        db_path: SQLite 파일 경로.

    Returns:
        마지막으로 송신한 seq. 송신할 게 없으면 ``since_seq`` 그대로.
    """
    rows = await asyncio.to_thread(
        _load_replay_payloads, db_path, session_id, since_seq
    )
    last = since_seq
    for seq, payload in rows:
        wire_json = f'{{"seq":{seq},"event":{payload}}}'
        await websocket.send_text(wire_json)
        last = seq
    return last


def _load_replay_payloads(
    db_path: Path, session_id: str, since_seq: int
) -> list[tuple[int, str]]:
    """``(seq, payload_json)`` 튜플을 seq 오름차순으로 반환한다.

    별도 connection 을 짧게 열고 닫는다 — replay 양이 많아도 메모리 부담 적음.

    Args:
        db_path: SQLite 파일 경로.
        session_id: 세션 식별자.
        since_seq: 초과 seq 임계값.

    Returns:
        ``(seq, payload)`` 튜플 리스트. payload 는 raw JSON 문자열.
    """
    conn = open_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT seq, payload FROM events WHERE session_id=? AND seq > ? ORDER BY seq ASC",
            (session_id, since_seq),
        ).fetchall()
        return [(int(r["seq"]), r["payload"]) for r in rows]
    finally:
        conn.close()
