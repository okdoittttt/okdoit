import pytest

from core.nodes.verify import MAX_CONSECUTIVE_ERRORS, MAX_LOOP_ITERATIONS, verify
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
        "consecutive_errors": 0,
        "last_action_error": None,
    }
    return {**base, **kwargs}


@pytest.mark.asyncio
async def test_verify_continues_loop_when_no_condition_met():
    """종료 조건이 없으면 is_done=False를 유지한다."""
    result = await verify(make_state())
    assert result["is_done"] is False
    assert result["error"] is None


@pytest.mark.asyncio
async def test_verify_error_increments_consecutive_and_continues():
    """첫 번째 에러는 루프를 종료하지 않고 consecutive_errors를 증가시킨다."""
    result = await verify(make_state(error="[act] 클릭 실패"))
    assert result["is_done"] is False
    assert result["consecutive_errors"] == 1
    assert result["last_action_error"] == "[act] 클릭 실패"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_verify_error_saves_to_last_action_error():
    """에러가 발생하면 last_action_error에 에러 메시지가 저장된다."""
    result = await verify(make_state(error="[act] 요소 없음"))
    assert result["last_action_error"] == "[act] 요소 없음"


@pytest.mark.asyncio
async def test_verify_clears_error_when_continuing():
    """에러 복구 시 error 필드가 None으로 클리어된다."""
    result = await verify(make_state(error="[act] Timeout"))
    assert result["error"] is None


@pytest.mark.asyncio
async def test_verify_stops_after_max_consecutive_errors():
    """연속 에러가 MAX_CONSECUTIVE_ERRORS에 도달하면 is_done=True로 종료한다."""
    result = await verify(make_state(
        error="[act] 클릭 실패",
        consecutive_errors=MAX_CONSECUTIVE_ERRORS - 1,
    ))
    assert result["is_done"] is True


@pytest.mark.asyncio
async def test_verify_continues_below_max_consecutive_errors():
    """연속 에러가 MAX_CONSECUTIVE_ERRORS 미만이면 루프를 계속한다."""
    result = await verify(make_state(
        error="[act] 클릭 실패",
        consecutive_errors=MAX_CONSECUTIVE_ERRORS - 2,
    ))
    assert result["is_done"] is False


@pytest.mark.asyncio
async def test_verify_resets_consecutive_errors_on_success():
    """에러 없이 성공하면 consecutive_errors가 0으로 리셋된다."""
    result = await verify(make_state(consecutive_errors=2))
    assert result["consecutive_errors"] == 0
    assert result["last_action_error"] is None


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
