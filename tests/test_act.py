import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from core.browser import BrowserManager
from core.nodes.act import _parse_action, act
from core.state import AgentState

load_dotenv()


def make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "https://example.com",
        "screenshot_path": None,
        "dom_text": None,
        "last_action": None,
        "is_done": False,
        "result": None,
        "error": None,
        "iterations": 0,
    }
    return {**base, **kwargs}


# ── _parse_action 단위 테스트 ──────────────────────────────────────────────────

def test_parse_action_navigate():
    """navigate JSON을 올바르게 파싱한다."""
    raw = json.dumps({"type": "navigate", "value": "https://google.com"})
    result = _parse_action(raw)
    assert result["type"] == "navigate"
    assert result["value"] == "https://google.com"


def test_parse_action_type():
    """type JSON을 올바르게 파싱한다."""
    raw = json.dumps({"type": "type", "target": "검색창", "value": "날씨"})
    result = _parse_action(raw)
    assert result["type"] == "type"
    assert result["target"] == "검색창"
    assert result["value"] == "날씨"


def test_parse_action_click():
    """click JSON을 올바르게 파싱한다."""
    raw = json.dumps({"type": "click", "value": "로그인 버튼"})
    result = _parse_action(raw)
    assert result["type"] == "click"
    assert result["value"] == "로그인 버튼"


def test_parse_action_scroll():
    """scroll JSON을 올바르게 파싱한다."""
    raw = json.dumps({"type": "scroll", "value": "down"})
    result = _parse_action(raw)
    assert result["type"] == "scroll"
    assert result["value"] == "down"


def test_parse_action_wait():
    """wait JSON을 올바르게 파싱한다."""
    raw = json.dumps({"type": "wait", "value": 2})
    result = _parse_action(raw)
    assert result["type"] == "wait"
    assert result["value"] == 2


def test_parse_action_invalid_json():
    """JSON이 아닌 문자열이면 error를 반환한다."""
    result = _parse_action("알 수 없는 명령어")
    assert "error" in result
    assert "[act]" in result["error"]


def test_parse_action_missing_type():
    """type 필드가 없으면 error를 반환한다."""
    raw = json.dumps({"value": "https://example.com"})
    result = _parse_action(raw)
    assert "error" in result
    assert "[act]" in result["error"]


# ── act() 단위 테스트 (browser mock) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_act_increments_iterations():
    """액션 성공 시 iterations가 1 증가하는지 확인한다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(last_action=json.dumps({"type": "navigate", "value": "https://example.com"})))

    assert result["iterations"] == 1


@pytest.mark.asyncio
async def test_act_increments_iterations_on_error():
    """에러 발생 시에도 iterations가 1 증가하는지 확인한다."""
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(side_effect=RuntimeError("not started"))

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(last_action=json.dumps({"type": "navigate", "value": "https://example.com"})))

    assert result["iterations"] == 1
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_act_records_error_on_unknown_action():
    """파싱 불가 액션이면 error 필드에 메시지를 기록하는지 확인한다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(last_action="알 수 없는 명령어"))

    assert result["error"] is not None
    assert "[act]" in result["error"]


@pytest.mark.asyncio
async def test_act_records_error_on_browser_not_ready():
    """브라우저가 없을 때 error 필드에 메시지를 기록하는지 확인한다."""
    result = await act(make_state(last_action=json.dumps({"type": "navigate", "value": "https://example.com"})))

    assert result["error"] is not None
    assert "[act]" in result["error"]


@pytest.mark.asyncio
async def test_act_clears_error_on_success():
    """성공 시 이전 error가 None으로 초기화되는지 확인한다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(last_action=json.dumps({"type": "navigate", "value": "https://example.com"}), error="이전 에러"))

    assert result["error"] is None


@pytest.mark.asyncio
async def test_act_skips_when_is_done():
    """is_done=True면 액션을 실행하지 않고 iterations만 증가시키는지 확인한다."""
    result = await act(make_state(is_done=True, last_action=json.dumps({"type": "wait", "value": 0}), iterations=1))
    assert result["is_done"] is True
    assert result["error"] is None
    assert result["iterations"] == 2


# ── last_action_result 필드 검증 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_act_records_success_last_action_result():
    """성공한 액션의 last_action_result는 success=True, error_code=None이다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(
            last_action=json.dumps({"type": "navigate", "value": "https://example.com"}),
        ))

    lar = result["last_action_result"]
    assert lar is not None
    assert lar["success"] is True
    assert lar["error_code"] is None
    assert lar["error_message"] is None


@pytest.mark.asyncio
async def test_act_records_failure_with_error_code():
    """실패한 액션의 last_action_result는 분류된 error_code와 복구 힌트를 담는다."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(side_effect=RuntimeError("클릭할 요소를 찾을 수 없습니다: '버튼'"))
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(
            last_action=json.dumps({"type": "navigate", "value": "https://example.com"}),
        ))

    lar = result["last_action_result"]
    assert lar["success"] is False
    assert lar["error_code"] == "element_not_found"
    assert lar["recovery_hint"] is not None
    # error 문자열에 error_code와 복구 힌트가 포함된다
    assert "error_code: element_not_found" in result["error"]
    assert "복구 힌트:" in result["error"]


@pytest.mark.asyncio
async def test_act_parse_error_records_invalid_argument():
    """JSON 파싱 실패는 INVALID_ARGUMENT로 기록된다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(last_action="이건 JSON 아님"))

    lar = result["last_action_result"]
    assert lar["success"] is False
    assert lar["error_code"] == "invalid_argument"


@pytest.mark.asyncio
async def test_act_extract_sets_extracted_result():
    """성공한 extract는 extracted_result를 채우고 last_action_result.extracted도 담는다."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="추출된 내용")
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager.current", return_value=mock_manager):
        result = await act(make_state(
            last_action=json.dumps({"type": "extract", "value": "h1"}),
        ))

    assert result["error"] is None
    assert result["extracted_result"] == "추출된 내용"
    assert result["last_action_result"]["extracted"] == "추출된 내용"


# ── act() 통합 테스트 ──────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_act_navigate_integration(tmp_path):
    """실제 브라우저에서 navigate 액션이 동작하는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()

    result = await act(make_state(last_action=json.dumps({"type": "navigate", "value": "https://example.com"})))

    page = await manager.get_page()
    assert result["error"] is None
    assert "example.com" in page.url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_act_scroll_integration(tmp_path):
    """실제 브라우저에서 scroll 액션이 에러 없이 동작하는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    result = await act(make_state(last_action=json.dumps({"type": "scroll", "value": "down"})))

    assert result["error"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_act_wait_integration(tmp_path):
    """실제 브라우저에서 wait 액션이 에러 없이 동작하는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    result = await act(make_state(last_action=json.dumps({"type": "wait", "value": 1})))

    assert result["error"] is None
