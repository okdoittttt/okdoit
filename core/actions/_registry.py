"""액션 레지스트리 - 액션 타입을 핸들러 함수에 매핑합니다."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional, Union

from langsmith import trace as ls_trace
from playwright.async_api import Page

from core.actions.result import ActionErrorCode, ActionResult, recovery_hint_for

# 핸들러 반환 타입. 마이그레이션 호환을 위해 세 가지를 모두 허용한다:
#   - ActionResult (권장, 명시적)
#   - str (성공 + extracted 데이터)
#   - None (성공)
# dispatch가 ActionResult로 정규화한다.
HandlerReturn = Union[ActionResult, str, None]
ActionHandler = Callable[[Page, dict], Awaitable[HandlerReturn]]


class ActionRegistry:
    """액션 타입 문자열을 핸들러 함수에 매핑하는 레지스트리.

    데코레이터 방식으로 핸들러를 등록하고, dispatch()로 실행한다. dispatch는
    핸들러 예외를 ActionResult.fail로 자동 변환하므로 핸들러는 실패 시 예외를
    그대로 던져도 된다(기존 스타일 호환).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, action_type: str) -> Callable[[ActionHandler], ActionHandler]:
        """액션 타입에 핸들러를 등록하는 데코레이터를 반환한다.

        Args:
            action_type: 등록할 액션 타입 문자열 (예: "navigate")

        Returns:
            함수를 그대로 반환하는 데코레이터
        """

        def decorator(fn: ActionHandler) -> ActionHandler:
            self._handlers[action_type] = fn
            return fn

        return decorator

    async def dispatch(self, page: Page, action: dict) -> ActionResult:
        """액션 타입에 맞는 핸들러를 찾아 실행하고 ActionResult로 돌려준다.

        처리 흐름:
            1. type 필드 검증 → 없거나 등록되지 않았으면 INVALID_ARGUMENT 실패
            2. 핸들러 실행 → 예외 발생 시 ActionResult.from_exception으로 분류
            3. 반환값 정규화:
                - ActionResult → 그대로
                - str → ActionResult.ok(extracted=...)
                - None/기타 → ActionResult.ok()

        Args:
            page: 현재 Playwright 페이지.
            action: _parse_action()이 반환한 액션 딕셔너리.

        Returns:
            ActionResult. 실패 시에도 예외를 던지지 않는다.
        """
        action_type = action.get("type")
        if not action_type:
            return ActionResult.fail(
                ActionErrorCode.INVALID_ARGUMENT,
                "액션에 type 필드가 없습니다.",
                recovery_hint_for(ActionErrorCode.INVALID_ARGUMENT),
            )

        handler = self._handlers.get(action_type)
        if handler is None:
            return ActionResult.fail(
                ActionErrorCode.INVALID_ARGUMENT,
                f"알 수 없는 액션 타입: '{action_type}'. 등록된 타입을 사용하세요.",
                recovery_hint_for(ActionErrorCode.INVALID_ARGUMENT),
            )

        with ls_trace(
            name="browser_action",
            inputs={"action_type": action_type, "params": {k: v for k, v in action.items() if k != "type"}},
            tags=["browser", "action"],
        ):
            try:
                raw = await handler(page, action)
            except Exception as exc:  # noqa: BLE001 - 매핑 후 구조화된 결과로 돌려준다
                return ActionResult.from_exception(exc)

        if isinstance(raw, ActionResult):
            return raw
        if isinstance(raw, str):
            return ActionResult.ok(extracted=raw)
        return ActionResult.ok()


registry = ActionRegistry()
