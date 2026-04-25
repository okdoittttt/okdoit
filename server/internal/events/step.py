"""``step.*`` 이벤트들 — 매 노드(observe/think/act/verify) 단계."""

from __future__ import annotations

from typing import Any, Literal, Optional

from server.internal.events.base import BaseEvent


class StepThinking(BaseEvent):
    """think 노드가 LLM 응답을 파싱한 직후 발행된다.

    Attributes:
        iteration: 해당 think 결과가 속한 반복 카운트(``AgentState.iterations``).
        thought: LLM 응답의 ``thought`` 필드(요약 / 추론 한 단락).
        action: LLM 이 결정한 액션 dict. 키는 액션 이름과 파라미터.
        memory_update: 해당 턴에 LLM 이 남긴 누적 메모리 갱신. 없으면 None.
    """

    type: Literal["step.thinking"] = "step.thinking"
    iteration: int
    thought: str
    action: dict[str, Any]
    memory_update: Optional[str] = None


class StepActed(BaseEvent):
    """act 노드가 액션 실행을 완료했을 때 발행된다.

    Attributes:
        action: 사람이 읽기 좋은 액션 시그니처(예: ``"click(index=12)"``).
        success: 액션 성공 여부.
        error_code: 실패 시 ``ActionResult`` 에러 코드. 없으면 None.
        error_message: 실패 시 사용자 메시지.
        extracted: 액션이 추출한 데이터(예: extract 액션의 결과).
    """

    type: Literal["step.acted"] = "step.acted"
    iteration: int
    action: str
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    extracted: Optional[Any] = None


class StepObserved(BaseEvent):
    """observe 노드가 DOM 인덱싱과 스크린샷을 마쳤을 때 발행된다.

    Attributes:
        current_url: 관측 시점의 페이지 URL.
        screenshot_path: 스크린샷의 sidecar 로컬 절대 경로. UI 는 정적 라우트로
            가져온다(추후, ``05-packaging-distribution.md`` 참조).
        interactive_count: ``selector_map`` 에 인덱싱된 요소 수.
    """

    type: Literal["step.observed"] = "step.observed"
    iteration: int
    current_url: str
    screenshot_path: Optional[str] = None
    interactive_count: int = 0


class StepVerified(BaseEvent):
    """verify 노드 완료 시 발행된다.

    Attributes:
        is_done: 루프 종료 신호.
        consecutive_errors: 누적 연속 에러 횟수.
    """

    type: Literal["step.verified"] = "step.verified"
    iteration: int
    is_done: bool
    consecutive_errors: int
