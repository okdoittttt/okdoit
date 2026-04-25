"""모든 sidecar 이벤트의 공통 베이스.

Pydantic 모델 계층의 공통 필드와 시간 헬퍼를 한 곳에 둔다. 도메인별 이벤트
파일(``session.py``, ``plan.py``, ``step.py``)은 여기를 import 한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    """현재 UTC 시각을 ISO 8601 문자열로 반환한다.

    Returns:
        ``2026-04-25T10:00:00.000000+00:00`` 형식의 문자열.
    """
    return datetime.now(timezone.utc).isoformat()


class BaseEvent(BaseModel):
    """모든 sidecar 이벤트의 공통 베이스.

    Attributes:
        session_id: 이벤트가 속한 세션 식별자(uuid4 문자열).
        ts: 이벤트 발생 시각(UTC ISO 8601).
    """

    session_id: str
    ts: str = Field(default_factory=utcnow_iso)
