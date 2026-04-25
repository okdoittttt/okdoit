"""``WS /sessions/{id}/events`` — 세션 이벤트 스트림."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.internal.deps import get_session_store
from server.internal.session import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

# 세션 미존재 시 close 코드. RFC 6455 의 4xxx 대역(애플리케이션 정의)을 사용.
WS_SESSION_NOT_FOUND_CODE: int = 4404


@router.websocket("/sessions/{session_id}/events")
async def session_events(
    websocket: WebSocket,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
) -> None:
    """세션 이벤트 스트림. 클라이언트는 한 세션당 1개만 연결한다.

    종료 조건:
        - runner 가 ``session.close_stream()`` 호출 → ``next_event()`` 가 None 반환
        - 클라이언트 disconnect → ``WebSocketDisconnect`` 예외
    """
    session = store.get(session_id)
    if session is None:
        await websocket.close(code=WS_SESSION_NOT_FOUND_CODE, reason="session not found")
        return

    await websocket.accept()
    logger.info("WS 연결: session_id=%s", session_id)
    try:
        while True:
            event = await session.next_event()
            if event is None:
                break
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WS disconnect: session_id=%s", session_id)
    except Exception:  # noqa: BLE001
        logger.exception("WS 핸들러 예외: session_id=%s", session_id)
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
