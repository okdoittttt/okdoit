"""ActionResult 및 예외 매핑 단위 테스트."""

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from core.actions.result import (
    ActionErrorCode,
    ActionResult,
    map_exception_to_code,
    recovery_hint_for,
)


# ── ActionResult.ok / fail / to_dict ─────────────────────────────────────────


def test_ok_defaults():
    """ok()는 success=True, 나머지는 None."""
    r = ActionResult.ok()
    assert r.success is True
    assert r.error_code is None
    assert r.error_message is None
    assert r.extracted is None
    assert r.recovery_hint is None


def test_ok_with_extracted():
    """ok(extracted=...)는 extracted 필드만 채운다."""
    r = ActionResult.ok(extracted="hello")
    assert r.success is True
    assert r.extracted == "hello"


def test_fail_auto_injects_default_hint():
    """fail에 hint를 지정하지 않으면 recovery_hint_for로 자동 주입된다."""
    r = ActionResult.fail(ActionErrorCode.TIMEOUT, "타임아웃")
    assert r.success is False
    assert r.error_code == ActionErrorCode.TIMEOUT
    assert r.error_message == "타임아웃"
    assert r.recovery_hint == recovery_hint_for(ActionErrorCode.TIMEOUT)
    assert r.recovery_hint is not None


def test_fail_with_explicit_hint_overrides_default():
    """hint를 명시하면 자동 주입되지 않는다."""
    r = ActionResult.fail(ActionErrorCode.TIMEOUT, "msg", hint="직접 힌트")
    assert r.recovery_hint == "직접 힌트"


def test_to_dict_serializes_enum_to_value():
    """to_dict는 error_code를 Enum이 아닌 문자열 값으로 직렬화한다."""
    r = ActionResult.fail(ActionErrorCode.ELEMENT_NOT_FOUND, "없음")
    d = r.to_dict()
    assert d["success"] is False
    assert d["error_code"] == "element_not_found"
    assert d["error_message"] == "없음"
    assert d["recovery_hint"] is not None
    assert d["extracted"] is None


def test_to_dict_for_ok():
    """ok는 error_code가 None으로 직렬화된다."""
    r = ActionResult.ok(extracted="foo")
    d = r.to_dict()
    assert d["success"] is True
    assert d["error_code"] is None
    assert d["error_message"] is None
    assert d["extracted"] == "foo"


def test_action_result_is_frozen():
    """ActionResult는 frozen dataclass라 mutation 불가."""
    r = ActionResult.ok()
    import dataclasses
    try:
        r.success = False  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:
        assert False, "frozen dataclass여야 한다"


# ── map_exception_to_code ────────────────────────────────────────────────────


def test_map_playwright_timeout_to_timeout_code():
    """Playwright TimeoutError는 TIMEOUT으로 매핑된다."""
    exc = PlaywrightTimeoutError("Timeout 30000ms exceeded waiting for locator")
    code, msg = map_exception_to_code(exc)
    assert code == ActionErrorCode.TIMEOUT
    assert msg  # 비어있지 않음


def test_map_not_visible_error():
    """'not visible' 메시지는 ELEMENT_NOT_VISIBLE."""
    code, _ = map_exception_to_code(Exception("Element is not visible"))
    assert code == ActionErrorCode.ELEMENT_NOT_VISIBLE


def test_map_not_in_viewport_error():
    """'not in viewport' 메시지도 ELEMENT_NOT_VISIBLE."""
    code, _ = map_exception_to_code(Exception("Target element is not in viewport"))
    assert code == ActionErrorCode.ELEMENT_NOT_VISIBLE


def test_map_intercepts_pointer_to_not_interactable():
    """'intercepts pointer' 메시지는 ELEMENT_NOT_INTERACTABLE."""
    code, _ = map_exception_to_code(Exception("Element intercepts pointer events"))
    assert code == ActionErrorCode.ELEMENT_NOT_INTERACTABLE


def test_map_detached_to_stale():
    """'detached' 메시지는 STALE_ELEMENT."""
    code, _ = map_exception_to_code(Exception("Element is detached from the DOM"))
    assert code == ActionErrorCode.STALE_ELEMENT


def test_map_korean_not_found_to_element_not_found():
    """한글 '찾을 수 없습니다' 메시지는 ELEMENT_NOT_FOUND로 매핑된다."""
    code, msg = map_exception_to_code(RuntimeError("클릭할 요소를 찾을 수 없습니다: '버튼'"))
    assert code == ActionErrorCode.ELEMENT_NOT_FOUND
    assert "버튼" in msg


def test_map_korean_not_appearing_to_element_not_found():
    """한글 '나타나지 않습니다' 메시지도 ELEMENT_NOT_FOUND."""
    code, _ = map_exception_to_code(RuntimeError("요소가 나타나지 않습니다: '로딩' (15초 초과)"))
    assert code == ActionErrorCode.ELEMENT_NOT_FOUND


def test_map_unknown_exception_to_unknown():
    """알 수 없는 예외는 UNKNOWN."""
    code, msg = map_exception_to_code(RuntimeError("정체불명의 오류"))
    assert code == ActionErrorCode.UNKNOWN
    assert "정체불명의 오류" in msg


def test_from_exception_builds_fail_with_hint():
    """from_exception은 기본 복구 힌트가 주입된 fail을 돌려준다."""
    r = ActionResult.from_exception(PlaywrightTimeoutError("timeout"))
    assert r.success is False
    assert r.error_code == ActionErrorCode.TIMEOUT
    assert r.recovery_hint == recovery_hint_for(ActionErrorCode.TIMEOUT)


# ── recovery_hint_for ─────────────────────────────────────────────────────────


def test_recovery_hint_for_all_codes_nonempty():
    """모든 ActionErrorCode에 대해 힌트가 존재하고 비어있지 않다."""
    for code in ActionErrorCode:
        hint = recovery_hint_for(code)
        assert isinstance(hint, str)
        assert len(hint) > 0
