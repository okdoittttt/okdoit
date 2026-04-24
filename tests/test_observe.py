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
    """dom_text에 [Page Info], [Interactive Elements], [Page Content] 섹션이 포함되는지 확인한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.goto("https://example.com")

    state = make_state()
    result = await observe(state)

    dom_text = result["dom_text"]
    assert "[Page Info]" in dom_text
    assert "[Interactive Elements]" in dom_text
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
    from core.nodes.observe import _apply_token_budget

    long_text = "A" * 10000
    trimmed = _apply_token_budget(long_text, max_tokens=2000)  # max_chars = 8000

    assert len(trimmed) <= 8100  # 약간의 여유 (생략 마크 포함)
    assert "...(이하 생략됨)" in trimmed
    assert trimmed.startswith("A" * 8000)


@pytest.mark.asyncio
async def test_trim_text_function_preserves_short_content():
    """토큰 제한 로직이 짧은 텍스트는 그대로 유지하는지 확인한다."""
    from core.nodes.observe import _apply_token_budget

    short_text = "Hello World"
    trimmed = _apply_token_budget(short_text, max_tokens=2000)

    assert trimmed == short_text
    assert "...(이하 생략됨)" not in trimmed


@pytest.mark.asyncio
async def test_observe_clickable_elements_deduplicates(tmp_path):
    """클릭 가능한 요소가 중복으로 수집되지 않는지 확인한다.

    예: <button onclick="submit()">제출</button>은 'button' 선택자와
    '[onclick]' 선택자에 모두 매칭되지만, 한 번만 수집되어야 한다.
    """
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()

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

    dom_text = result["dom_text"]
    interactive_section = dom_text.split("[Page Content]")[0]

    submit_count = interactive_section.count("Submit")
    assert submit_count == 1, f"Submit 버튼이 {submit_count}번 나타났습니다 (중복 발생)"


# ── 인덱싱 (selector_map + data-oi-idx) 통합 테스트 ─────────────────────────


@pytest.mark.asyncio
async def test_observe_populates_selector_map(tmp_path):
    """observe가 상호작용 요소들을 selector_map에 인덱스별로 저장한다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.set_content("""
    <html><body>
      <button>확인</button>
      <a href="/next">다음</a>
      <input type="text" placeholder="검색">
    </body></html>
    """)

    state = make_state()
    result = await observe(state)

    smap = result["selector_map"]
    assert isinstance(smap, dict)
    assert len(smap) >= 3
    # 키는 0부터 순차
    assert 0 in smap
    # 각 항목은 필수 필드 보유
    first = smap[0]
    assert "tag" in first
    assert "text" in first
    assert "attributes" in first
    assert "bbox" in first
    # 태그 셋이 예상과 맞음
    tags = {e["tag"] for e in smap.values()}
    assert {"button", "a", "input"}.issubset(tags)


@pytest.mark.asyncio
async def test_observe_assigns_data_oi_idx_attribute(tmp_path):
    """observe 후 각 요소에 data-oi-idx 속성이 심긴다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.set_content("""
    <html><body>
      <button id="b1">첫번째</button>
      <button id="b2">두번째</button>
    </body></html>
    """)

    state = make_state()
    result = await observe(state)

    smap = result["selector_map"]
    assert len(smap) == 2
    # DOM에 실제로 속성이 심겼는지 확인
    b1_idx = await page.get_attribute("#b1", "data-oi-idx")
    b2_idx = await page.get_attribute("#b2", "data-oi-idx")
    assert b1_idx is not None
    assert b2_idx is not None
    assert b1_idx != b2_idx
    # selector_map의 키와 일치
    assert int(b1_idx) in smap
    assert int(b2_idx) in smap


@pytest.mark.asyncio
async def test_observe_interactive_elements_format(tmp_path):
    """[Interactive Elements] 섹션에 [N]<tag ...>text</tag> 포맷으로 표시된다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.set_content("""
    <html><body>
      <button>확인</button>
      <a href="/x">링크</a>
    </body></html>
    """)

    state = make_state()
    result = await observe(state)

    dom_text = result["dom_text"]
    # 적어도 [0]으로 시작하는 라인이 섹션 안에 있어야 한다
    assert "[Interactive Elements]" in dom_text
    assert "[0]<" in dom_text
    # 태그명이 프롬프트에 노출된다
    assert "<button" in dom_text or "<a" in dom_text


@pytest.mark.asyncio
async def test_observe_reindexes_on_next_call(tmp_path):
    """연속 observe 호출 시 이전 data-oi-idx는 제거되고 새 인덱스가 부여된다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.set_content("""
    <html><body>
      <button>1</button>
      <button>2</button>
      <button>3</button>
    </body></html>
    """)

    await observe(make_state())
    # DOM 변경: 첫 버튼 제거
    await page.evaluate("document.querySelectorAll('button')[0].remove()")
    result2 = await observe(make_state())

    # 두 번째 observe 이후 남아있는 data-oi-idx 속성 수 = 남은 버튼 수
    remaining = await page.evaluate("document.querySelectorAll('[data-oi-idx]').length")
    assert remaining == 2
    assert len(result2["selector_map"]) == 2
    # 인덱스는 0, 1 로 재부여됨
    assert set(result2["selector_map"].keys()) == {0, 1}


@pytest.mark.asyncio
async def test_observe_empty_page_has_empty_selector_map(tmp_path):
    """상호작용 요소가 없는 페이지는 빈 selector_map을 갖는다."""
    manager = BrowserManager(headless=True, screenshot_dir=str(tmp_path))
    await manager.start()
    page = await manager.get_page()
    await page.set_content("<html><body><p>텍스트만 있는 페이지</p></body></html>")

    result = await observe(make_state())

    assert result["selector_map"] == {}
    assert "(상호작용 가능한 요소 없음)" in result["dom_text"]


# ── _format_element_line 단위 테스트 ─────────────────────────────────────────


def test_format_element_line_button_with_text():
    """텍스트 있는 button은 <tag>text</tag> 형식으로 포맷된다."""
    from core.nodes.observe import _format_element_line
    elem = {"index": 3, "tag": "button", "role": None, "text": "확인", "attributes": {}, "bbox": [0, 0, 0, 0]}
    line = _format_element_line(elem)
    assert line == "[3]<button>확인</button>"


def test_format_element_line_input_void():
    """input은 텍스트가 있어도 자기완결(void) 태그로 포맷된다."""
    from core.nodes.observe import _format_element_line
    elem = {"index": 1, "tag": "input", "role": None, "text": "", "attributes": {"type": "email", "placeholder": "이메일"}, "bbox": [0, 0, 0, 0]}
    line = _format_element_line(elem)
    assert line.startswith("[1]<input")
    assert line.endswith("/>")
    assert 'type="email"' in line
    assert 'placeholder="이메일"' in line


def test_format_element_line_link_with_href():
    """a는 href 속성과 텍스트가 함께 포맷된다."""
    from core.nodes.observe import _format_element_line
    elem = {"index": 0, "tag": "a", "role": None, "text": "로그인", "attributes": {"href": "/login"}, "bbox": [0, 0, 0, 0]}
    line = _format_element_line(elem)
    assert line == '[0]<a href="/login">로그인</a>'


def test_format_element_line_truncates_long_text():
    """80자 초과 텍스트는 말줄임표로 잘린다."""
    from core.nodes.observe import _format_element_line
    long_text = "가" * 200
    elem = {"index": 0, "tag": "button", "role": None, "text": long_text, "attributes": {}, "bbox": [0, 0, 0, 0]}
    line = _format_element_line(elem)
    assert "…" in line
    # 200자 원본보다 훨씬 짧아야 한다 (태그 래퍼 포함해도)
    assert len(line) < len(long_text)
    # 텍스트 부분(태그 래퍼 제외)은 80자 이하
    inner = line.removeprefix("[0]<button>").removesuffix("</button>")
    assert len(inner) <= 80