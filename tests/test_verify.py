import json

import pytest

from core.nodes.verify import (
    ACTION_HISTORY_MAX,
    LOOP_STOP_THRESHOLD,
    LOOP_WARN_THRESHOLD,
    MAX_CONSECUTIVE_ERRORS,
    MAX_LOOP_ITERATIONS,
    _action_signature,
    _detect_loop,
    _update_action_history,
    verify,
)
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
        "action_history": [],
    }
    return {**base, **kwargs}


def action_json(**fields) -> str:
    """테스트 편의 헬퍼: last_action 포맷(JSON 문자열)을 만든다."""
    return json.dumps(fields, ensure_ascii=False)


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


# ── _action_signature 단위 테스트 ─────────────────────────────────────────────

def test_action_signature_basic_click():
    """click/value 액션의 시그니처를 추출한다."""
    sig = _action_signature(action_json(type="click", value="로그인"))
    assert sig == "click:로그인"


def test_action_signature_includes_index_and_value():
    """index와 value가 모두 있으면 둘 다 시그니처에 포함된다."""
    sig = _action_signature(action_json(type="click_index", index=7, value="ignored_not_in_key_order"))
    # _SIG_KEY_FIELDS 순서: index, value, target, source
    assert sig == "click_index:7:ignored_not_in_key_order"


def test_action_signature_ignores_incidental_fields():
    """timeout 등 부수 파라미터는 시그니처에 포함되지 않는다."""
    sig_a = _action_signature(action_json(type="wait_for_element", value="버튼", timeout=10))
    sig_b = _action_signature(action_json(type="wait_for_element", value="버튼", timeout=30))
    assert sig_a == sig_b
    assert "timeout" not in sig_a


def test_action_signature_truncates_long_value():
    """매우 긴 value는 잘라낸다."""
    long_value = "x" * 500
    sig = _action_signature(action_json(type="type", value=long_value))
    # 40자 제한
    assert sig == f"type:{'x' * 40}"


def test_action_signature_non_json_returns_none():
    """JSON이 아닌 last_action 문자열은 None을 반환한다(집계 제외)."""
    assert _action_signature("자유 텍스트 액션") is None


def test_action_signature_none_returns_none():
    """last_action이 None이면 None을 반환한다."""
    assert _action_signature(None) is None


def test_action_signature_empty_string_returns_none():
    """빈 문자열이면 None을 반환한다."""
    assert _action_signature("") is None


def test_action_signature_non_dict_returns_none():
    """JSON이 dict가 아니면 None을 반환한다."""
    assert _action_signature(json.dumps([1, 2, 3])) is None


def test_action_signature_same_type_different_values_differ():
    """같은 타입이어도 value가 다르면 다른 시그니처."""
    s1 = _action_signature(action_json(type="click", value="A"))
    s2 = _action_signature(action_json(type="click", value="B"))
    assert s1 != s2


# ── _update_action_history 단위 테스트 ───────────────────────────────────────

def test_update_action_history_appends():
    """새 시그니처가 history 끝에 추가된다."""
    result = _update_action_history(["a", "b"], "c")
    assert result == ["a", "b", "c"]


def test_update_action_history_none_signature_is_ignored():
    """시그니처가 None이면 history가 변경되지 않고 사본을 돌려준다."""
    history = ["a", "b"]
    result = _update_action_history(history, None)
    assert result == history
    assert result is not history  # 원본 변경 방지


def test_update_action_history_trims_to_max():
    """ACTION_HISTORY_MAX를 초과하는 앞부분은 버려진다."""
    many = [f"sig{i}" for i in range(ACTION_HISTORY_MAX + 3)]
    result = _update_action_history(many, "new")
    assert len(result) == ACTION_HISTORY_MAX
    assert result[-1] == "new"
    # 가장 오래된 4개는 제거 (ACTION_HISTORY_MAX + 3 + 1 → 뒤 ACTION_HISTORY_MAX개)
    assert result[0] == f"sig{4}"


def test_update_action_history_does_not_mutate_original():
    """원본 history는 변경되지 않는다."""
    history = ["a"]
    _update_action_history(history, "b")
    assert history == ["a"]


# ── _detect_loop 단위 테스트 ─────────────────────────────────────────────────

def test_detect_loop_empty_returns_none():
    assert _detect_loop([]) is None


def test_detect_loop_insufficient_data_returns_none():
    """warn 임계값보다 적으면 None."""
    assert _detect_loop(["a"] * (LOOP_WARN_THRESHOLD - 1)) is None


def test_detect_loop_warn_when_exactly_warn_threshold_same():
    """LOOP_WARN_THRESHOLD 회 연속 동일이면 warn."""
    assert _detect_loop(["a"] * LOOP_WARN_THRESHOLD) == "warn"


def test_detect_loop_stop_when_stop_threshold_same():
    """LOOP_STOP_THRESHOLD 회 연속 동일이면 stop."""
    assert _detect_loop(["a"] * LOOP_STOP_THRESHOLD) == "stop"


def test_detect_loop_stop_takes_precedence():
    """stop 조건이 충족되면 warn이 아닌 stop을 반환한다."""
    # LOOP_STOP_THRESHOLD보다 많이 반복되는 경우도 stop
    assert _detect_loop(["a"] * (LOOP_STOP_THRESHOLD + 2)) == "stop"


def test_detect_loop_mixed_tail_returns_none():
    """최근 꼬리에 다른 시그니처가 섞이면 None."""
    # warn 임계값 직전까지 같지만 마지막이 다름
    history = ["a", "a", "b"]
    assert _detect_loop(history) is None


def test_detect_loop_old_repetition_cleared_by_new_action():
    """과거에 반복이 있었어도 최근 꼬리가 다양하면 None."""
    history = ["a", "a", "a", "b", "c"]
    assert _detect_loop(history) is None


# ── verify LoopDetector 통합 테스트 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_stops_on_loop_detection():
    """LOOP_STOP_THRESHOLD 회 연속 동일 액션이 누적되면 강제 종료한다."""
    sig = "click:같은버튼"
    prior = [sig] * (LOOP_STOP_THRESHOLD - 1)
    result = await verify(make_state(
        last_action=action_json(type="click", value="같은버튼"),
        action_history=prior,
    ))
    assert result["is_done"] is True
    assert result["error"] is not None
    assert "강제 종료" in result["error"]
    assert result["result"] == "동일 액션 반복으로 강제 종료했습니다."


@pytest.mark.asyncio
async def test_verify_warn_injects_hint_when_no_error():
    """LOOP_WARN_THRESHOLD 회 연속이지만 stop 전이면 last_action_error에 경고 힌트를 넣는다."""
    sig = "click:같은버튼"
    # 누적 후 warn 임계값이 되도록
    prior = [sig] * (LOOP_WARN_THRESHOLD - 1)
    result = await verify(make_state(
        last_action=action_json(type="click", value="같은버튼"),
        action_history=prior,
    ))
    assert result["is_done"] is False
    assert result["last_action_error"] is not None
    assert "연속 같은 액션" in result["last_action_error"]


@pytest.mark.asyncio
async def test_verify_warn_merged_with_existing_action_error():
    """act 에러와 루프 warn이 동시 발생 시 last_action_error에 두 메시지가 병합된다."""
    sig = "click:같은버튼"
    prior = [sig] * (LOOP_WARN_THRESHOLD - 1)
    result = await verify(make_state(
        last_action=action_json(type="click", value="같은버튼"),
        action_history=prior,
        error="[act] 클릭 실패",
    ))
    assert result["is_done"] is False
    merged = result["last_action_error"]
    assert merged is not None
    assert "[act] 클릭 실패" in merged
    assert "[루프 경고]" in merged


@pytest.mark.asyncio
async def test_verify_updates_action_history():
    """verify는 매 호출마다 last_action의 시그니처를 action_history에 누적한다."""
    result = await verify(make_state(
        last_action=action_json(type="click", value="로그인"),
        action_history=["wait:2"],
    ))
    assert result["action_history"] == ["wait:2", "click:로그인"]


@pytest.mark.asyncio
async def test_verify_trims_action_history_to_max():
    """action_history가 ACTION_HISTORY_MAX를 넘지 않는다."""
    saturated = [f"sig{i}" for i in range(ACTION_HISTORY_MAX)]
    result = await verify(make_state(
        last_action=action_json(type="click", value="새로운버튼"),
        action_history=saturated,
    ))
    assert len(result["action_history"]) == ACTION_HISTORY_MAX
    assert result["action_history"][-1] == "click:새로운버튼"
    assert "sig0" not in result["action_history"]


@pytest.mark.asyncio
async def test_verify_no_loop_when_varied_actions():
    """다양한 액션이 섞여 있으면 loop 판정하지 않고 정상 진행한다."""
    history = ["click:A", "scroll:down", "click:B", "wait:2"]
    result = await verify(make_state(
        last_action=action_json(type="navigate", value="https://example.com"),
        action_history=history,
    ))
    assert result["is_done"] is False
    assert result["last_action_error"] is None


@pytest.mark.asyncio
async def test_verify_loop_stop_takes_priority_over_error_recovery():
    """loop stop이 감지되면 error 복구 로직보다 우선 종료한다."""
    sig = "click:같은버튼"
    prior = [sig] * (LOOP_STOP_THRESHOLD - 1)
    # error도 있지만 loop stop이 우선
    result = await verify(make_state(
        last_action=action_json(type="click", value="같은버튼"),
        action_history=prior,
        error="[act] 클릭 실패",
        consecutive_errors=0,
    ))
    assert result["is_done"] is True
    assert "강제 종료" in result["error"]


@pytest.mark.asyncio
async def test_verify_handles_non_json_last_action_gracefully():
    """last_action이 JSON이 아니면 action_history에 추가되지 않지만 에러는 없다."""
    result = await verify(make_state(
        last_action="자유 텍스트",
        action_history=["click:A"],
    ))
    assert result["is_done"] is False
    assert result["action_history"] == ["click:A"]  # 변경 없음
