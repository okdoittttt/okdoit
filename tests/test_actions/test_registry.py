"""ActionRegistry 단위 테스트."""

import pytest
from unittest.mock import AsyncMock

from core.actions import ActionRegistry
from core.actions.result import ActionErrorCode, ActionResult


@pytest.fixture
def fresh_registry():
    """테스트 격리를 위한 새 레지스트리."""
    return ActionRegistry()


@pytest.mark.asyncio
async def test_register_and_dispatch(fresh_registry):
    """register()로 등록한 핸들러가 dispatch()로 호출되는지 확인한다."""
    mock_handler = AsyncMock()

    @fresh_registry.register("test_action")
    async def handler(page, action):
        await mock_handler(page, action)

    mock_page = AsyncMock()
    action = {"type": "test_action", "value": "x"}
    await fresh_registry.dispatch(mock_page, action)

    mock_handler.assert_called_once_with(mock_page, action)


@pytest.mark.asyncio
async def test_dispatch_unknown_type_returns_invalid_argument(fresh_registry):
    """등록되지 않은 타입은 예외가 아닌 ActionResult.fail(INVALID_ARGUMENT)로 돌아온다."""
    mock_page = AsyncMock()
    action = {"type": "unknown_xyz"}

    result = await fresh_registry.dispatch(mock_page, action)

    assert isinstance(result, ActionResult)
    assert result.success is False
    assert result.error_code == ActionErrorCode.INVALID_ARGUMENT
    assert "unknown_xyz" in (result.error_message or "")


@pytest.mark.asyncio
async def test_dispatch_missing_type_returns_invalid_argument(fresh_registry):
    """type 필드 자체가 없어도 ActionResult.fail(INVALID_ARGUMENT)."""
    mock_page = AsyncMock()

    result = await fresh_registry.dispatch(mock_page, {})

    assert result.success is False
    assert result.error_code == ActionErrorCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_dispatch_normalizes_none_return_to_ok(fresh_registry):
    """핸들러가 None을 반환하면 ActionResult.ok()로 정규화된다(호환성)."""

    @fresh_registry.register("legacy_none")
    async def handler(page, action):
        return None

    result = await fresh_registry.dispatch(AsyncMock(), {"type": "legacy_none"})
    assert result.success is True
    assert result.extracted is None


@pytest.mark.asyncio
async def test_dispatch_normalizes_str_return_to_extracted(fresh_registry):
    """핸들러가 str을 반환하면 ActionResult.ok(extracted=str)로 정규화된다."""

    @fresh_registry.register("legacy_str")
    async def handler(page, action):
        return "hello"

    result = await fresh_registry.dispatch(AsyncMock(), {"type": "legacy_str"})
    assert result.success is True
    assert result.extracted == "hello"


@pytest.mark.asyncio
async def test_dispatch_passes_through_action_result(fresh_registry):
    """핸들러가 ActionResult를 반환하면 그대로 전달된다."""

    @fresh_registry.register("native")
    async def handler(page, action):
        return ActionResult.fail(ActionErrorCode.TIMEOUT, "직접 fail")

    result = await fresh_registry.dispatch(AsyncMock(), {"type": "native"})
    assert result.success is False
    assert result.error_code == ActionErrorCode.TIMEOUT
    assert result.error_message == "직접 fail"


@pytest.mark.asyncio
async def test_dispatch_converts_exception_to_fail(fresh_registry):
    """핸들러가 예외를 던지면 ActionResult.from_exception으로 변환된다."""

    @fresh_registry.register("boom")
    async def handler(page, action):
        raise RuntimeError("클릭할 요소를 찾을 수 없습니다: '버튼'")

    result = await fresh_registry.dispatch(AsyncMock(), {"type": "boom"})
    assert result.success is False
    assert result.error_code == ActionErrorCode.ELEMENT_NOT_FOUND
    assert "버튼" in (result.error_message or "")
    assert result.recovery_hint is not None  # 기본 힌트 주입


def test_register_returns_original_function(fresh_registry):
    """register() 데코레이터가 원본 함수를 그대로 반환하는지 확인한다."""

    async def my_handler(page, action):
        pass

    result = fresh_registry.register("foo")(my_handler)
    assert result is my_handler


def test_register_overwrites_existing_handler(fresh_registry):
    """같은 타입을 두 번 등록하면 마지막 것으로 덮어쓰는지 확인한다."""
    call_log = []

    @fresh_registry.register("dup")
    async def first(page, action):
        call_log.append("first")

    @fresh_registry.register("dup")
    async def second(page, action):
        call_log.append("second")

    assert fresh_registry._handlers["dup"] is second


@pytest.mark.asyncio
async def test_global_registry_has_all_actions():
    """전역 registry에 7개 기본 액션이 모두 등록되어 있는지 확인한다."""
    from core.actions import registry

    for action_type in ("navigate", "click", "type", "scroll", "wait", "press", "back"):
        assert action_type in registry._handlers, f"{action_type} 미등록"
