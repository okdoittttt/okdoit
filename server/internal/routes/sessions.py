"""``/sessions/...`` — 조회 / 일시정지 / 재개 / 중단 / 아티팩트.

PR3 부터 조회 라우트(``GET /sessions``, ``GET /sessions/{id}``, ``GET .../artifact``)
는 활성 캐시뿐 아니라 SQLite DB 도 본다. 활성/비활성 모두 같은 라우트로 노출되므로
sidecar 재시작 후에도 사이드바와 결과 화면이 그대로 복원된다.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
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

logger = logging.getLogger(__name__)

# 정적 라우트 prefix. ``app.py`` 의 ``StaticFiles`` 마운트 경로와 동기화해야 한다.
SCREENSHOT_URL_PREFIX: str = "/static/screenshots"

# 활성 세션 DELETE 시 graceful stop 을 기다릴 최대 시간(초). 이를 넘기면 force evict.
# runner 가 stop_event 를 무시하는 hang edge case 에 대비. 일반 노드는 수 백 ms 내 종료.
_GRACEFUL_STOP_TIMEOUT_S: float = 10.0

# graceful stop 폴링 간격(초). status 가 sync 로 갱신되므로 짧게 둬도 부담 없음.
_TERMINAL_POLL_INTERVAL_S: float = 0.1

# 종료 상태 집합. 이 집합에 들어오면 runner 가 더 이상 publish 하지 않는다.
_TERMINAL_STATUSES: frozenset[SessionStatus] = frozenset(
    {SessionStatus.FINISHED, SessionStatus.ERRORED, SessionStatus.STOPPED}
)

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


@router.delete("/{session_id}", response_model=OkResponse)
async def delete_session(
    session_id: str,
    store: SqliteSessionStore = Depends(get_session_store),
    settings: ServerSettings = Depends(get_settings),
) -> OkResponse:
    """세션을 영구 삭제한다 (DB row + 자식 테이블 + 디스크 스크린샷).

    활성 세션이면 graceful stop 을 먼저 요청하고 terminal status 까지 기다린다.
    runner 가 hang 됐을 때를 대비해 ``_GRACEFUL_STOP_TIMEOUT_S`` 안에 종료 안 되면
    force evict 한 뒤 그래도 삭제는 진행한다 — 사용자가 명시적으로 삭제를 눌렀으므로
    "남기는" 게 더 큰 사고.

    Args:
        session_id: 경로 파라미터.
        store: 활성 캐시 + DB 둘 다 다루는 store.
        settings: 스크린샷 디렉토리 결정에 쓰는 설정.

    Returns:
        ``OkResponse``.

    Raises:
        HTTPException: 활성/DB 어디에도 없으면 status 404.
    """
    active = store.get(session_id)
    if active is not None:
        active.request_stop()
        try:
            await asyncio.wait_for(
                _await_terminal(active),
                timeout=_GRACEFUL_STOP_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "세션 %s graceful stop timeout(%.1fs) — force evict 진행",
                session_id,
                _GRACEFUL_STOP_TIMEOUT_S,
            )
        store.evict(session_id)

    deleted = await asyncio.to_thread(store.delete_persisted, session_id)
    if deleted == 0 and active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"세션을 찾을 수 없습니다: {session_id}",
        )

    # 디스크 스크린샷 디렉토리 정리. FK CASCADE 는 DB 메타만 처리함.
    screenshot_dir = settings.screenshot_dir / session_id
    if screenshot_dir.exists():
        await asyncio.to_thread(
            shutil.rmtree, screenshot_dir, ignore_errors=True
        )

    return OkResponse()


async def _await_terminal(session: Session) -> None:
    """세션이 FINISHED / ERRORED / STOPPED 중 하나가 될 때까지 폴링한다.

    runner 가 노드 사이에서 ``stop_event`` 를 감지해 status 를 sync 로 set 하므로
    별도 동기화 primitive 없이 status 폴링으로 충분하다.

    Args:
        session: 대기할 활성 세션.
    """
    while session.status not in _TERMINAL_STATUSES:
        await asyncio.sleep(_TERMINAL_POLL_INTERVAL_S)


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
