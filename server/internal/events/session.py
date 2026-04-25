"""``session.*`` 이벤트들 — 세션 라이프사이클.

세션 생성, 종료, 에러, 일시정지, 재개, 중단의 6가지 상태 전이를 표현한다.
"""

from __future__ import annotations

from typing import Literal, Optional

from server.internal.events.base import BaseEvent


class SessionStarted(BaseEvent):
    """``POST /run`` 으로 세션이 시작됐을 때 발행된다.

    Attributes:
        task: 사용자 입력 태스크 문자열.
    """

    type: Literal["session.started"] = "session.started"
    task: str


class SessionFinished(BaseEvent):
    """그래프가 정상 종료되어 결과가 확정됐을 때 발행된다.

    Attributes:
        result: 최종 결과 텍스트. ``AgentState.result`` 또는 ``extracted_result``.
        iterations: 종료 시점의 반복 횟수.
    """

    type: Literal["session.finished"] = "session.finished"
    result: Optional[str] = None
    iterations: int = 0


class SessionErrored(BaseEvent):
    """그래프 실행 중 복구 불가 에러로 종료됐을 때 발행된다.

    Attributes:
        error: 실패 원인 메시지(사람이 읽기 좋은 한 줄).
    """

    type: Literal["session.errored"] = "session.errored"
    error: str


class SessionPaused(BaseEvent):
    """사용자가 ``pause`` 를 호출해 다음 노드 진입이 멈춘 직후 발행된다."""

    type: Literal["session.paused"] = "session.paused"


class SessionResumed(BaseEvent):
    """사용자가 ``resume`` 을 호출해 멈춤이 해제된 직후 발행된다."""

    type: Literal["session.resumed"] = "session.resumed"


class SessionStopped(BaseEvent):
    """사용자가 ``stop`` 을 호출해 루프가 중단됐을 때 발행된다."""

    type: Literal["session.stopped"] = "session.stopped"
