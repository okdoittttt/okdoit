"""``/health`` — sidecar 기동 확인 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter

from server.internal.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """헬스체크. main process 의 sidecar 기동 확인용.

    Returns:
        ``{"status": "ok", "protocol_version": ...}``.
    """
    return HealthResponse()
