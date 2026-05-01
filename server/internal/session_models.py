"""``Session`` / ``SessionStore`` 와 Repository 가 공유하는 도메인 enum + 모델.

별도 파일로 분리한 이유: ``session.py`` 가 Repository 를 쓰고, Repository 가
``SessionStatus`` / ``SessionSnapshot`` 을 쓰는 양방향 의존을 끊는 것. Pydantic /
enum 정의만 두고 의존성이 없도록 한다.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class SessionStatus(str, Enum):
    """세션 라이프사이클 상태."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ERRORED = "errored"
    STOPPED = "stopped"


class SessionSnapshot(BaseModel):
    """``GET /sessions/{id}`` 응답용 직렬화 스냅샷.

    런타임 객체(``Session``) 자체에는 asyncio primitive 가 들어있어
    그대로 직렬화할 수 없다. DB row 도 같은 표현으로 환산된다.

    Attributes:
        id: 세션 식별자(uuid4).
        task: 사용자가 입력한 작업 문자열.
        status: 현재 라이프사이클 상태(``SessionStatus``).
        iterations: 가장 최근에 본 ``AgentState["iterations"]`` 값.
        result: 정상 종료 시 결과 텍스트. 미종료 / 실패 시 None.
        error: 에러 종료 시 메시지. 정상 / 미종료 시 None.
    """

    id: str
    task: str
    status: SessionStatus
    iterations: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
