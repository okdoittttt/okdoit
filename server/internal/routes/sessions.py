"""``/sessions/...`` — 조회 / 일시정지 / 재개 / 중단 / 아티팩트.

PR3 부터 조회 라우트(``GET /sessions``, ``GET /sessions/{id}``, ``GET .../artifact``)
는 활성 캐시뿐 아니라 SQLite DB 도 본다. 활성/비활성 모두 같은 라우트로 노출되므로
sidecar 재시작 후에도 사이드바와 결과 화면이 그대로 복원된다.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from server.internal.config import ServerSettings, get_settings
from server.internal.deps import get_session, get_session_store
from server.internal.events import SessionPaused, SessionResumed
from server.internal.schemas import OkResponse, SessionArtifact
from server.internal.session import (
    Session,
    SessionSnapshot,
    SessionStatus,
    SqliteSessionStore,
)

# 정적 라우트 prefix. ``app.py`` 의 ``StaticFiles`` 마운트 경로와 동기화해야 한다.
SCREENSHOT_URL_PREFIX: str = "/static/screenshots"

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSnapshot])
async def list_sessions(
    store: SqliteSessionStore = Depends(get_session_store),
) -> list[SessionSnapshot]:
    """DB 의 최근 세션 스냅샷 목록을 반환한다 (활성 + 비활성)."""
    return store.list_all()


@router.get("/{session_id}", response_model=SessionSnapshot)
async def get_session_snapshot_route(
    session_id: str,
    store: SqliteSessionStore = Depends(get_session_store),
) -> SessionSnapshot:
    """단일 세션 스냅샷을 반환한다.

    활성 세션이면 인메모리 ``Session.snapshot()`` 이 우선 — 그 객체가 진행 중
    상태의 단일 진실원이고 DB 는 조금 늦게 따라간다. 비활성(과거) 세션만 DB row
    로 폴백한다.

    Raises:
        HTTPException: 활성/DB 어디에도 없으면 status 404.
    """
    active = store.get(session_id)
    if active is not None:
        return active.snapshot()
    snap = store.snapshot_of(session_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"세션을 찾을 수 없습니다: {session_id}",
        )
    return snap


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
    session_id: str,
    store: SqliteSessionStore = Depends(get_session_store),
    settings: ServerSettings = Depends(get_settings),
) -> SessionArtifact:
    """세션 결과물 한 묶음을 반환한다.

    활성 캐시에 있으면 인메모리 ``Session`` 의 최신 필드를 그대로 노출하고,
    비활성(과거) 세션은 DB row + 스크린샷 메타로 재구성한다. v1 은 artifacts
    테이블을 미사용 — ``subtasks`` / ``collected_data`` 는 비활성 응답에서 빈 값.

    Args:
        session_id: 경로 파라미터.
        store: 활성 캐시 + DB 둘 다 보는 store.
        settings: 스크린샷 루트 결정에 쓰는 sidecar 설정.

    Returns:
        ``SessionArtifact`` — 결과 텍스트 + subtasks + 스크린샷 URL 목록 + 추출 데이터.

    Raises:
        HTTPException: 활성/비활성 어디에도 없으면 status 404.
    """
    active = store.get(session_id)
    if active is not None:
        return SessionArtifact(
            id=active.id,
            task=active.task,
            status=active.status,
            iterations=active.latest_iterations,
            result=active.latest_result,
            error=active.latest_error,
            subtasks=list(active.latest_subtasks),
            screenshots=[
                _to_screenshot_url(p, settings.screenshot_dir)
                for p in active.screenshot_paths
            ],
            collected_data=dict(active.latest_collected_data),
        )

    snap = store.snapshot_of(session_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"세션을 찾을 수 없습니다: {session_id}",
        )
    paths = store.screenshot_paths_for(session_id)
    return SessionArtifact(
        id=snap.id,
        task=snap.task,
        status=snap.status,
        iterations=snap.iterations,
        result=snap.result,
        error=snap.error,
        subtasks=[],
        screenshots=[_to_screenshot_url(p, settings.screenshot_dir) for p in paths],
        collected_data={},
    )


def _to_screenshot_url(path: str, screenshot_root: Path) -> str:
    """스크린샷 절대 경로를 정적 라우트 URL 로 변환한다.

    가능한 경우 ``screenshot_root`` 기준 상대 경로를 그대로 URL 에 옮겨
    sub-dir 정보를 보존한다(예: ``<root>/<sid>/step_1.png`` →
    ``/static/screenshots/<sid>/step_1.png``). 루트 밖의 경로면 basename 만 사용해
    fallback 한다.

    Args:
        path: 스크린샷 파일의 sidecar 로컬 경로.
        screenshot_root: ``settings.screenshot_dir`` 의 절대 경로 기준점.

    Returns:
        ``/static/screenshots/...`` 형태의 상대 URL.
    """
    abs_path = Path(path).resolve()
    try:
        rel = abs_path.relative_to(screenshot_root.resolve())
    except ValueError:
        rel = Path(abs_path.name)
    return f"{SCREENSHOT_URL_PREFIX}/{rel.as_posix()}"
