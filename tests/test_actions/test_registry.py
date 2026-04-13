"""ActionRegistry 단위 테스트."""

import pytest
from unittest.mock import AsyncMock

from core.actions import ActionRegistry


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
async def test_dispatch_unknown_type_raises_value_error(fresh_registry):
    """등록되지 않은 타입을 dispatch하면 ValueError가 발생하는지 확인한다."""
    mock_page = AsyncMock()
    action = {"type": "unknown_xyz"}

    with pytest.raises(ValueError, match=r"\[act\].*unknown_xyz"):
        await fresh_registry.dispatch(mock_page, action)


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
    """전역 registry에 5개 기본 액션이 모두 등록되어 있는지 확인한다."""
    from core.actions import registry

    for action_type in ("navigate", "click", "type", "scroll", "wait"):
        assert action_type in registry._handlers, f"{action_type} 미등록"
