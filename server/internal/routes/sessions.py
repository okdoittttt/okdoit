"""``/sessions/...`` — 조회 / 일시정지 / 재개 / 중단 / 아티팩트."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from server.internal.deps import get_session, get_session_store
from server.internal.events import SessionPaused, SessionResumed
from server.internal.schemas import OkResponse, SessionArtifact
from server.internal.session import Session, SessionSnapshot, SessionStatus, SessionStore

# 정적 라우트 prefix. ``app.py`` 의 ``StaticFiles`` 마운트 경로와 동기화해야 한다.
SCREENSHOT_URL_PREFIX: str = "/static/screenshots"

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


@router.get("/{session_id}/artifact", response_model=SessionArtifact)
async def get_session_artifact(
    session: Session = Depends(get_session),
) -> SessionArtifact:
    """세션 종료 후 결과물 한 묶음을 반환한다.

    스크린샷 파일은 ``StaticFiles`` 로 마운트된 ``/static/screenshots/<filename>``
    URL 로 변환해서 노출한다(클라이언트가 ``<img src>`` 로 바로 사용 가능).

    Args:
        session: 의존성 주입된 ``Session``.

    Returns:
        ``SessionArtifact`` — 결과 텍스트 + subtasks + 스크린샷 URL 목록 + 추출 데이터.
    """
    return SessionArtifact(
        id=session.id,
        task=session.task,
        status=session.status,
        iterations=session.latest_iterations,
        result=session.latest_result,
        error=session.latest_error,
        subtasks=list(session.latest_subtasks),
        screenshots=[_to_screenshot_url(p) for p in session.screenshot_paths],
        collected_data=dict(session.latest_collected_data),
    )


def _to_screenshot_url(path: str) -> str:
    """절대 경로를 정적 라우트 URL 로 변환한다.

    Args:
        path: 스크린샷 파일의 sidecar 로컬 경로.

    Returns:
        ``/static/screenshots/<basename>`` 형태의 상대 URL. 클라이언트가 sidecar
        베이스 URL 과 합쳐서 ``http://127.0.0.1:PORT/static/screenshots/...`` 로 사용.
    """
    return f"{SCREENSHOT_URL_PREFIX}/{Path(path).name}"
