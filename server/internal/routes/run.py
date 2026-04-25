"""``/run`` — 새 작업 세션을 만들고 백그라운드로 그래프를 실행한다."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Depends, status

from core.browser import BrowserManager
from server.internal.config import ServerSettings, get_settings
from server.internal.deps import get_session_store
from server.internal.runner import AgentRunner
from server.internal.schemas import RunRequest, RunResponse
from server.internal.session import SessionStore

logger = logging.getLogger(__name__)

# 스크린샷 루트 디렉토리. 세션마다 ``<root>/<session_id>/`` sub-dir 에 저장한다.
# ``server.internal.app`` 의 ``SCREENSHOT_DIR_NAME`` 과 동기화.
SCREENSHOT_ROOT: str = ".screenshots"

router = APIRouter(tags=["run"])


@router.post("/run", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def run_task(
    req: RunRequest,
    settings: ServerSettings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
) -> RunResponse:
    """새 세션을 만들고 ``AgentRunner`` 를 백그라운드 태스크로 띄운다.

    스크린샷은 ``.screenshots/<session_id>/`` 안에 저장한다 — 세션 간 파일명
    충돌(서로의 ``step_N.png`` 를 덮어 써 ResultPanel 갤러리가 섞이는 문제) 방지.

    Args:
        req: ``RunRequest``.
        settings: 주입된 sidecar 설정.
        store: 주입된 ``SessionStore``.

    Returns:
        ``{"session_id": ...}``.
    """
    headless = req.headless if req.headless is not None else settings.headless_default
    session = store.create(task=req.task)
    screenshot_dir = os.path.join(SCREENSHOT_ROOT, session.id)
    manager = BrowserManager(headless=headless, screenshot_dir=screenshot_dir)
    runner = AgentRunner(session=session, manager=manager)

    asyncio.create_task(runner.run(), name=f"agent-runner-{session.id}")
    logger.info("세션 시작: id=%s task=%s headless=%s", session.id, req.task, headless)
    return RunResponse(session_id=session.id)
