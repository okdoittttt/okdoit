import pytest

from core.nodes.verify import MAX_LOOP_ITERATIONS, verify
from core.state import AgentState


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "https://example.com",
        "screenshot_path": None,
        "dom_text": None,
        "last_action": "로그인 버튼 클릭",
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 0,
    }
    return {**base, **kwargs}


@pytest.mark.asyncio
async def test_verify_continues_loop_when_no_condition_met():
    """종료 조건이 없으면 is_done=False를 유지한다."""
    result = await verify(make_state())
    assert result["is_done"] is False
    assert result["error"] is None


@pytest.mark.asyncio
async def test_verify_stops_on_error():
    """error가 있으면 is_done=True로 에러 종료한다."""
    result = await verify(make_state(error="[act] Timeout"))
    assert result["is_done"] is True
    assert result["error"] == "[act] Timeout"


@pytest.mark.asyncio
async def test_verify_stops_on_max_iterations():
    """iterations가 MAX_LOOP_ITERATIONS를 초과하면 비정상 종료한다."""
    result = await verify(make_state(iterations=MAX_LOOP_ITERATIONS + 1))
    assert result["is_done"] is True
    assert result["error"] is not None
    assert "[verify]" in result["error"]
    assert result["result"] == "최대 반복 횟수를 초과했습니다."


@pytest.mark.asyncio
async def test_verify_does_not_stop_at_exact_max_iterations():
    """iterations가 MAX_LOOP_ITERATIONS와 같으면 루프를 계속한다."""
    result = await verify(make_state(iterations=MAX_LOOP_ITERATIONS))
    assert result["is_done"] is False


@pytest.mark.asyncio
async def test_verify_stops_on_is_done_true():
    """think에서 is_done=True로 판단했으면 정상 종료한다."""
    result = await verify(make_state(is_done=True, result="작업 완료"))
    assert result["is_done"] is True
    assert result["result"] == "작업 완료"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_verify_error_takes_priority_over_is_done():
    """error와 is_done이 동시에 있으면 error 처리가 먼저다."""
    result = await verify(make_state(is_done=True, error="[act] 오류 발생"))
    assert result["is_done"] is True
    assert result["error"] == "[act] 오류 발생"


@pytest.mark.asyncio
async def test_verify_error_takes_priority_over_max_iterations():
    """error와 max iterations 초과가 동시에 있으면 error 처리가 먼저다."""
    result = await verify(make_state(
        iterations=MAX_LOOP_ITERATIONS + 1,
        error="[act] 오류 발생",
    ))
    assert result["is_done"] is True
    assert result["error"] == "[act] 오류 발생"
    assert result["result"] is None
