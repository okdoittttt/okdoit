"""이벤트 패키지 진입점.

도메인별 모듈에 흩어진 이벤트 클래스를 한곳에서 re-export 하고,
``ServerEvent`` 디스크리미네이트 유니온과 envelope 를 정의한다.

호출 측은 항상 ``from server.internal.events import ...`` 로 가져간다(내부 분할은
호출 측에 노출되지 않는다).
"""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import BaseModel, Field

from server.internal.events.base import BaseEvent, utcnow_iso
from server.internal.events.plan import PlanCreated, PlanReplanned, SubtaskActivated
from server.internal.events.session import (
    SessionErrored,
    SessionFinished,
    SessionPaused,
    SessionResumed,
    SessionStarted,
    SessionStopped,
)
from server.internal.events.step import StepActed, StepObserved, StepThinking, StepVerified

__all__ = [
    "BaseEvent",
    "PlanCreated",
    "PlanReplanned",
    "ServerEvent",
    "ServerEventEnvelope",
    "SessionErrored",
    "SessionFinished",
    "SessionPaused",
    "SessionResumed",
    "SessionStarted",
    "SessionStopped",
    "StepActed",
    "StepObserved",
    "StepThinking",
    "StepVerified",
    "SubtaskActivated",
    "utcnow_iso",
]


ServerEvent = Annotated[
    Union[
        SessionStarted,
        SessionFinished,
        SessionErrored,
        SessionPaused,
        SessionResumed,
        SessionStopped,
        PlanCreated,
        PlanReplanned,
        SubtaskActivated,
        StepThinking,
        StepActed,
        StepObserved,
        StepVerified,
    ],
    Field(discriminator="type"),
]
"""모든 이벤트 클래스를 ``type`` 필드로 판별하는 합집합.

``ServerEventEnvelope.model_validate(payload)`` 로 역직렬화 가능. UI 측에서는
TypeScript 타입을 수동 동기화한다(자동 생성은 추후 도입).
"""


class ServerEventEnvelope(BaseModel):
    """단일 이벤트를 한 번에 (역)직렬화하기 위한 래퍼.

    WebSocket 송신 시에는 이벤트 자체가 ``type`` 필드를 들고 있어 그대로
    ``model_dump_json()`` 하면 된다. 이 envelope 는 테스트 / 외부 입력 검증 용도다.

    Attributes:
        event: ``ServerEvent`` 합집합 중 하나. ``type`` 리터럴로 클래스가
            판별되어 역직렬화된다.
    """

    event: ServerEvent
