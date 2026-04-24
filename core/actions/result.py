"""액션 실행 결과의 구조화된 표현.

모든 액션 핸들러는 성공 시 ``ActionResult.ok()`` (또는 ``.ok(extracted=...)``) 를
반환하고, 실패는 예외를 그대로 던지거나 명시적으로 ``ActionResult.fail(...)`` 을
반환한다. ``ActionRegistry.dispatch`` 는 예외를 catch해 ``ActionResult`` 로 변환한다.

act 노드가 이 구조를 state로 옮기고, verify 노드가 ``error_code`` 별 복구 힌트를
``last_action_error`` 에 실어 다음 턴 think 에 전달한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ActionErrorCode(str, Enum):
    """액션 실패의 분류 코드.

    LLM 프롬프트에 그대로 노출되므로 이름은 명확하고 안정적이어야 한다.
    """

    ELEMENT_NOT_FOUND = "element_not_found"
    ELEMENT_NOT_VISIBLE = "element_not_visible"
    ELEMENT_NOT_INTERACTABLE = "element_not_interactable"
    STALE_ELEMENT = "stale_element"
    TIMEOUT = "timeout"
    NAVIGATION_FAILED = "navigation_failed"
    INVALID_ARGUMENT = "invalid_argument"
    UNKNOWN = "unknown"


# 에러 코드별 기본 복구 힌트. LLM이 다음 턴에 대안 전략을 시도할 때 참고한다.
_RECOVERY_HINTS: dict[ActionErrorCode, str] = {
    ActionErrorCode.ELEMENT_NOT_FOUND: (
        "DOM이 바뀌었을 수 있습니다. 스크롤·scroll_to_element로 요소를 화면에 나타내거나, "
        "페이지가 로딩 중이면 wait 후 재시도하세요. 다른 텍스트/요소도 후보로 고려."
    ),
    ActionErrorCode.ELEMENT_NOT_VISIBLE: (
        "scroll_to_element로 요소를 viewport로 이동시키거나, 덮고 있는 모달/팝업을 먼저 닫으세요."
    ),
    ActionErrorCode.ELEMENT_NOT_INTERACTABLE: (
        "다른 요소가 상호작용을 가로막고 있습니다. 모달을 닫거나 오버레이를 제거한 후 재시도."
    ),
    ActionErrorCode.STALE_ELEMENT: (
        "직전 네비게이션/DOM 변경으로 요소 참조가 무효해졌습니다. 다음 턴에서 observe가 재수행되면 해결됩니다."
    ),
    ActionErrorCode.TIMEOUT: (
        "네트워크·렌더링이 느릴 수 있습니다. wait로 1~2초 대기 후 재시도하거나 URL을 직접 navigate."
    ),
    ActionErrorCode.NAVIGATION_FAILED: (
        "URL과 네트워크 상태를 확인하세요. wait 후 재시도 또는 refresh로 복구를 시도."
    ),
    ActionErrorCode.INVALID_ARGUMENT: (
        "액션 파라미터 스펙을 다시 확인하세요. [액션 스키마]의 필드명과 타입을 점검."
    ),
    ActionErrorCode.UNKNOWN: (
        "원인이 불명확합니다. 다른 접근(URL 직접 이동, 다른 요소 선택, refresh)으로 우회를 시도."
    ),
}


def recovery_hint_for(code: ActionErrorCode) -> str:
    """에러 코드에 대응하는 기본 복구 힌트 문자열을 반환한다.

    Args:
        code: 분류된 에러 코드.

    Returns:
        프롬프트에 바로 붙일 수 있는 한 문장 힌트.
    """
    return _RECOVERY_HINTS.get(code, _RECOVERY_HINTS[ActionErrorCode.UNKNOWN])


@dataclass(frozen=True)
class ActionResult:
    """액션 실행의 구조화된 결과.

    Attributes:
        success: 의도대로 실행됐으면 True.
        error_code: 실패 시 분류 코드. 성공 시 None.
        error_message: LLM에 노출할 한 줄 한글 메시지. 성공 시 None.
        extracted: extract/execute_js처럼 텍스트를 돌려주는 액션의 결과. 성공·실패 무관.
        recovery_hint: 실패 시 LLM에 제공하는 복구 힌트. 성공 시 None.
    """

    success: bool
    error_code: Optional[ActionErrorCode] = None
    error_message: Optional[str] = None
    extracted: Optional[str] = None
    recovery_hint: Optional[str] = None

    @classmethod
    def ok(cls, extracted: Optional[str] = None) -> "ActionResult":
        """성공 결과를 생성한다.

        Args:
            extracted: 액션이 돌려주는 데이터 문자열. 대부분의 액션은 None.

        Returns:
            success=True인 ActionResult.
        """
        return cls(success=True, extracted=extracted)

    @classmethod
    def fail(
        cls,
        code: ActionErrorCode,
        message: str,
        hint: Optional[str] = None,
    ) -> "ActionResult":
        """실패 결과를 생성한다.

        Args:
            code: 분류된 에러 코드.
            message: 사용자(LLM)에 노출할 짧은 한글 메시지.
            hint: 생략하면 ``recovery_hint_for(code)`` 가 기본값으로 사용된다.

        Returns:
            success=False인 ActionResult.
        """
        return cls(
            success=False,
            error_code=code,
            error_message=message,
            recovery_hint=hint if hint is not None else recovery_hint_for(code),
        )

    @classmethod
    def from_exception(cls, exc: BaseException) -> "ActionResult":
        """예외를 ActionResult.fail로 변환한다.

        registry.dispatch에서 모든 handler 예외에 대해 호출된다.

        Args:
            exc: 핸들러가 던진 예외.

        Returns:
            분류된 에러 코드와 한글 메시지, 기본 복구 힌트를 담은 ActionResult.
        """
        code, message = map_exception_to_code(exc)
        return cls.fail(code, message)

    def to_dict(self) -> dict[str, Any]:
        """LangGraph state에 넣을 수 있는 JSON 친화 dict로 직렬화한다.

        ActionErrorCode는 문자열 value로 치환된다.
        """
        return {
            "success": self.success,
            "error_code": self.error_code.value if self.error_code else None,
            "error_message": self.error_message,
            "extracted": self.extracted,
            "recovery_hint": self.recovery_hint,
        }


def map_exception_to_code(exc: BaseException) -> tuple[ActionErrorCode, str]:
    """Playwright/표준 예외를 ActionErrorCode와 한글 메시지로 매핑한다.

    우선순위:
        1. Playwright TimeoutError 인스턴스 체크 → TIMEOUT
        2. 예외 메시지 문자열 매칭으로 세부 분류

    메시지 매칭은 Playwright 버전에 따라 변할 수 있어 1차 방어선은 isinstance.

    Args:
        exc: 분류할 예외.

    Returns:
        (코드, 한글 메시지) 튜플. 메시지는 기존 예외 문구를 최대한 보존한다.
    """
    from playwright.async_api import TimeoutError as PwTimeout

    if isinstance(exc, PwTimeout):
        return ActionErrorCode.TIMEOUT, "지정한 시간 내에 요소를 찾지 못했습니다."

    original = str(exc)
    lower = original.lower()

    if "not visible" in lower or "not in viewport" in lower:
        return ActionErrorCode.ELEMENT_NOT_VISIBLE, "요소가 화면에 보이지 않습니다."
    if "intercepts pointer" in lower or "not clickable" in lower:
        return ActionErrorCode.ELEMENT_NOT_INTERACTABLE, "다른 요소가 상호작용을 가로막고 있습니다."
    if "detached" in lower or "stale" in lower:
        return ActionErrorCode.STALE_ELEMENT, "요소가 더 이상 DOM에 존재하지 않습니다."
    if (
        "no element" in lower
        or "찾을 수 없습니다" in original
        or "나타나지 않습니다" in original
    ):
        return ActionErrorCode.ELEMENT_NOT_FOUND, original or "요소를 찾지 못했습니다."
    if "net::" in lower or "navigation" in lower:
        return ActionErrorCode.NAVIGATION_FAILED, original or "네비게이션 실패."

    return ActionErrorCode.UNKNOWN, original or f"알 수 없는 오류: {type(exc).__name__}"
