import os
import pytest
import pytest_asyncio
from core.browser import BrowserManager
from core.nodes.observe import observe
from core.state import AgentState


def make_state(**kwargs) -> AgentState:
    """테스트용 기본 AgentState를 생성한다.

    Args:
        **kwargs: 기본값을 덮어쓸 AgentState 필드.

    Returns:
        테스트용 AgentState.
    """
    base: AgentState = {
        "task": "테스트 태스크",
        "messages": [],
        "current_url": "",
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
    """각 테스트 전후로 싱글톤 인스턴스를 초기화한다."""
    BrowserManager._instance = None
    yield
    if BrowserManager._instance is not None:
        await BrowserManager._instance.stop()


@pytest.mark.asyncio
async def test_observe_without_browser_returns_error():
    """브라우저 시작 없이 observe 호출 시 error 필드에 메시지가 기록되는지 확인한다."""
    state = make_state()
    result = await observe(state)
    assert result["error"] is not None
    assert "[observe]" in result["error"]


@pytest.mark.asyncio
async def test_observe_updates_screenshot_path(tmp_path):
    """observe 호출 후 screenshot_path가 업데이트되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state(iterations=1)
    result = await observe(state)

    assert result["screenshot_path"] is not None
    assert os.path.exists(result["screenshot_path"])
    assert "step_1.png" in result["screenshot_path"]


@pytest.mark.asyncio
async def test_observe_updates_current_url(tmp_path):
    """observe 호출 후 current_url이 업데이트되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state()
    result = await observe(state)

    assert result["current_url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_observe_updates_dom_text(tmp_path):
    """observe 호출 후 dom_text가 추출되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state()
    result = await observe(state)

    assert result["dom_text"] is not None
    assert len(result["dom_text"]) > 0


@pytest.mark.asyncio
async def test_observe_clears_previous_error(tmp_path):
    """이전 error가 있던 state에서 observe 성공 시 error가 None으로 초기화되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state(error="이전 에러 메시지")
    result = await observe(state)

    assert result["error"] is None


@pytest.mark.asyncio
async def test_observe_screenshot_filename_matches_iterations(tmp_path):
    """스크린샷 파일명이 iterations 값을 반영하는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state(iterations=5)
    result = await observe(state)

    assert "step_5.png" in result["screenshot_path"]


@pytest.mark.asyncio
async def test_observe_dom_text_contains_page_info_sections(tmp_path):
    """dom_text에 [Page Info], [Clickable Elements], [Page Content] 섹션이 포함되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state()
    result = await observe(state)

    dom_text = result["dom_text"]
    assert "[Page Info]" in dom_text
    assert "[Clickable Elements]" in dom_text
    assert "[Page Content]" in dom_text
    assert "Title:" in dom_text
    assert "URL:" in dom_text


@pytest.mark.asyncio
async def test_observe_dom_text_includes_url(tmp_path):
    """dom_text에 현재 URL이 포함되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state()
    result = await observe(state)

    assert "https://example.com/" in result["dom_text"]


@pytest.mark.asyncio
async def test_observe_dom_text_includes_page_title(tmp_path):
    """dom_text에 페이지 title이 포함되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state()
    result = await observe(state)

    # example.com의 title은 "Example Domain"
    assert "Title:" in result["dom_text"]
    assert len(result["dom_text"]) > 0


@pytest.mark.asyncio
async def test_trim_text_function_handles_long_content():
    """토큰 제한 로직이 긴 텍스트를 제대로 자르는지 확인한다."""
    from core.nodes.observe import _trim_text

    long_text = "A" * 10000
    trimmed = _trim_text(long_text, max_chars=8000)

    assert len(trimmed) <= 8100  # 약간의 여유 (중괄호, 마크 포함)
    assert "...[중략]..." in trimmed
    assert trimmed.startswith("A" * int(8000 * 0.6))


@pytest.mark.asyncio
async def test_trim_text_function_preserves_short_content():
    """토큰 제한 로직이 짧은 텍스트는 그대로 유지하는지 확인한다."""
    from core.nodes.observe import _trim_text

    short_text = "Hello World"
    trimmed = _trim_text(short_text, max_chars=8000)

    assert trimmed == short_text
    assert "...[중략]..." not in trimmed


@pytest.mark.asyncio
async def test_observe_clickable_elements_deduplicates(tmp_path):
    """클릭 가능한 요소가 중복으로 수집되지 않는지 확인한다.

    예: <button onclick="submit()">제출</button>은 'button' 선택자와
    '[onclick]' 선택자에 모두 매칭되지만, 한 번만 수집되어야 한다.
    """
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()

    # onclick 속성을 가진 button을 포함하는 HTML 페이지
    html_content = """
    <html>
    <body>
    <button onclick="alert('test')">Submit</button>
    <input type="text" placeholder="Search">
    <a href="/home">Home</a>
    </body>
    </html>
    """
    await page.set_content(html_content)

    state = make_state()
    result = await observe(state)

    # dom_text에서 클릭 가능한 요소 섹션 추출
    dom_text = result["dom_text"]
    clickable_section = dom_text.split("[Page Content]")[0]

    # Submit 버튼이 한 번만 나타나는지 확인 (중복 제거 검증)
    submit_count = clickable_section.count("Submit")
    assert submit_count == 1, f"Submit 버튼이 {submit_count}번 나타났습니다 (중복 발생)"