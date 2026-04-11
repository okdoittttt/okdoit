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


@pytest_asyncio.fixture(autouse=True)
async def reset_singleton():
    BrowserManager._instance = None
    yield
    if BrowserManager._instance is not None:
        await BrowserManager._instance.stop()


# ── _parse_action 단위 테스트 ──────────────────────────────────────────────────

def test_parse_action_navigate():
    """URL이 포함된 문자열을 navigate로 파싱한다."""
    result = _parse_action("https://google.com으로 이동")
    assert result["type"] == "navigate"
    assert result["value"] == "https://google.com"


def test_parse_action_navigate_bare_url():
    """URL만 있는 문자열을 navigate로 파싱한다."""
    result = _parse_action("https://example.com")
    assert result["type"] == "navigate"
    assert result["value"] == "https://example.com"


def test_parse_action_type_with_quotes():
    """따옴표가 있는 입력 액션을 파싱한다."""
    result = _parse_action("검색창에 '날씨' 입력")
    assert result["type"] == "type"
    assert result["target"] == "검색창"
    assert result["value"] == "날씨"


def test_parse_action_type_without_quotes():
    """따옴표 없는 입력 액션을 파싱한다."""
    result = _parse_action("이메일 입력창에 test@example.com 입력")
    assert result["type"] == "type"
    assert result["target"] == "이메일 입력창"
    assert result["value"] == "test@example.com"


def test_parse_action_scroll_down():
    """아래 스크롤 액션을 파싱한다."""
    result = _parse_action("아래로 스크롤")
    assert result["type"] == "scroll"
    assert result["value"] == "down"


def test_parse_action_scroll_up():
    """위 스크롤 액션을 파싱한다."""
    result = _parse_action("위로 스크롤")
    assert result["type"] == "scroll"
    assert result["value"] == "up"


def test_parse_action_wait():
    """대기 액션을 파싱한다."""
    result = _parse_action("2초 대기")
    assert result["type"] == "wait"
    assert result["value"] == 2.0


def test_parse_action_wait_decimal():
    """소수점 대기 시간을 파싱한다."""
    result = _parse_action("1.5초 대기")
    assert result["type"] == "wait"
    assert result["value"] == 1.5


def test_parse_action_click():
    """클릭 액션을 파싱한다."""
    result = _parse_action("로그인 버튼 클릭")
    assert result["type"] == "click"
    assert result["value"] == "로그인 버튼"


def test_parse_action_unknown():
    """파싱할 수 없는 액션은 error를 반환한다."""
    result = _parse_action("알 수 없는 명령어")
    assert "error" in result
    assert "[act]" in result["error"]


# ── act() 단위 테스트 (browser mock) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_act_increments_iterations():
    """액션 성공 시 iterations가 1 증가하는지 확인한다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager", return_value=mock_manager):
        result = await act(make_state(last_action="https://example.com으로 이동"))

    assert result["iterations"] == 1


@pytest.mark.asyncio
async def test_act_increments_iterations_on_error():
    """에러 발생 시에도 iterations가 1 증가하는지 확인한다."""
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(side_effect=RuntimeError("not started"))

    with patch("core.nodes.act.BrowserManager", return_value=mock_manager):
        result = await act(make_state(last_action="https://example.com으로 이동"))

    assert result["iterations"] == 1
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_act_records_error_on_unknown_action():
    """파싱 불가 액션이면 error 필드에 메시지를 기록하는지 확인한다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager", return_value=mock_manager):
        result = await act(make_state(last_action="알 수 없는 명령어"))

    assert result["error"] is not None
    assert "[act]" in result["error"]


@pytest.mark.asyncio
async def test_act_records_error_on_browser_not_ready():
    """브라우저가 없을 때 error 필드에 메시지를 기록하는지 확인한다."""
    result = await act(make_state(last_action="https://example.com으로 이동"))

    assert result["error"] is not None
    assert "[act]" in result["error"]


@pytest.mark.asyncio
async def test_act_clears_error_on_success():
    """성공 시 이전 error가 None으로 초기화되는지 확인한다."""
    mock_page = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.get_page = AsyncMock(return_value=mock_page)

    with patch("core.nodes.act.BrowserManager", return_value=mock_manager):
        result = await act(make_state(last_action="https://example.com으로 이동", error="이전 에러"))

    assert result["error"] is None


@pytest.mark.asyncio
async def test_act_skips_when_is_done():
    """is_done=True면 액션을 실행하지 않고 iterations만 증가시키는지 확인한다."""
    result = await act(make_state(is_done=True, last_action="없음", iterations=1))
    assert result["is_done"] is True
    assert result["error"] is None
    assert result["iterations"] == 2


# ── act() 통합 테스트 ──────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_act_navigate_integration(tmp_path):
    """실제 브라우저에서 navigate 액션이 동작하는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()

    result = await act(make_state(last_action="https://example.com으로 이동"))

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

    result = await act(make_state(last_action="아래로 스크롤"))

    assert result["error"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_act_wait_integration(tmp_path):
    """실제 브라우저에서 wait 액션이 에러 없이 동작하는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    result = await act(make_state(last_action="1초 대기"))

    assert result["error"] is None
