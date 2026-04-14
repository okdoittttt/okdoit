"""액션 레지스트리 - 액션 타입을 핸들러 함수에 매핑합니다."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

from langsmith import traceable
from playwright.async_api import Page

ActionHandler = Callable[[Page, dict], Awaitable[Optional[str]]]


class ActionRegistry:
    """액션 타입 문자열을 핸들러 함수에 매핑하는 레지스트리.

    데코레이터 방식으로 핸들러를 등록하고, dispatch()로 실행한다.
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

    @traceable(name="browser_action", tags=["browser", "action"])
    async def dispatch(self, page: Page, action: dict) -> Optional[str]:
        """액션 타입에 맞는 핸들러를 찾아 실행한다.

        Args:
            page: 현재 Playwright 페이지
            action: _parse_action()이 반환한 액션 딕셔너리

        Returns:
            핸들러가 반환한 문자열 데이터. 대부분의 액션은 None을 반환한다.

        Raises:
            ValueError: 등록되지 않은 액션 타입인 경우
        """
        action_type = action["type"]
        handler = self._handlers.get(action_type)
        if handler is None:
            raise ValueError(f"[act] 알 수 없는 액션 타입: '{action_type}'")
        return await handler(page, action)


registry = ActionRegistry()
