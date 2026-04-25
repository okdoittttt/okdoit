"""``/sessions/...`` — 조회 / 일시정지 / 재개 / 중단."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from server.internal.deps import get_session, get_session_store
from server.internal.events import SessionPaused, SessionResumed
from server.internal.schemas import OkResponse
from server.internal.session import Session, SessionSnapshot, SessionStatus, SessionStore

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSnapshot])
async def list_sessions(
    store: SessionStore = Depends(get_session_store),
) -> list[SessionSnapshot]:
    """현재 살아있는 세션 스냅샷 목록을 반환한다."""
    return [s.snapshot() for s in store.list_all()]


@router.get("/{session_id}", response_model=SessionSnapshot)
async def get_session_snapshot(
    session: Session = Depends(get_session),
) -> SessionSnapshot:
    """단일 세션의 스냅샷을 반환한다."""
    return session.snapshot()


@router.post("/{session_id}/pause", response_model=OkResponse)
async def pause_session(
    session: Session = Depends(get_session),
) -> OkResponse:
    """세션을 다음 노드 진입 직전에 일시정지하도록 요청한다.

    Raises:
        HTTPException: 세션이 RUNNING / PAUSED 이외의 상태면 status 409.
    """
    if session.status not in {SessionStatus.RUNNING, SessionStatus.PAUSED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"세션이 {session.status.value} 상태라 pause 할 수 없습니다.",
        )
    session.pause()
    await session.publish(SessionPaused(session_id=session.id))
    return OkResponse()


@router.post("/{session_id}/resume", response_model=OkResponse)
async def resume_session(
    session: Session = Depends(get_session),
) -> OkResponse:
    """일시정지된 세션을 재개한다.

    Raises:
        HTTPException: 세션이 PAUSED 가 아니면 status 409.
    """
    if session.status != SessionStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"세션이 {session.status.value} 상태라 resume 할 수 없습니다.",
        )
    session.resume()
    await session.publish(SessionResumed(session_id=session.id))
    return OkResponse()


@router.post("/{session_id}/stop", response_model=OkResponse)
async def stop_session(
    session: Session = Depends(get_session),
) -> OkResponse:
    """세션 루프 중단을 요청한다. 실제 종료는 다음 노드 경계에서 일어난다."""
    session.request_stop()
    return OkResponse()
