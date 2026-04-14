from typing import Any

from langsmith import trace as ls_trace
from playwright.async_api import Page

from core.browser import BrowserManager
from core.state import AgentState

MAX_CHARS = 8000
MAX_CLICKABLE_ELEMENTS = 30


async def observe(state: AgentState) -> AgentState:
    """현재 브라우저 상태를 관찰하고 state를 업데이트한다.

    The Loop의 첫 번째 노드. 스크린샷 촬영, 구조화된 DOM 정보 추출, 현재 URL을 수집해
    state에 기록한다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        screenshot_path, dom_text, current_url이 업데이트된 AgentState.
        에러 발생 시 error 필드에 메시지를 기록하고 반환한다.
    """
    try:
        manager = BrowserManager()
        page = await manager.get_page()

        filename = f"step_{state['iterations']}.png"
        screenshot_path = await manager.take_screenshot(filename)

        dom_text = await _extract_structured_dom(page)
        current_url = page.url

        return {
            **state,
            "screenshot_path": screenshot_path,
            "dom_text": dom_text,
            "current_url": current_url,
            "iterations": state["iterations"] + 1,
            "error": None,
        }
    except RuntimeError as e:
        return {**state, "error": f"[observe] Browser not ready: {e}"}
    except Exception as e:
        return {**state, "error": f"[observe] Unexpected error: {e}"}


async def _extract_structured_dom(page: Page) -> str:
    """페이지에서 구조화된 DOM 정보를 추출하고 포맷한다.

    페이지 메타데이터(title, url, description), 클릭 가능한 요소,
    본문 텍스트를 수집하여 LLM이 이해하기 쉬운 형식으로 반환한다.

    Args:
        page: 정보를 추출할 Playwright 페이지 객체

    Returns:
        포맷된 DOM 정보 문자열. 추출 실패 시 에러 메시지를 반환한다.
    """
    try:
        url = page.url
        with ls_trace(
            name="browser_extract_dom",
            inputs={"url": url},
            tags=["browser", "observe"],
        ):
            title = await page.title()
            meta_description = await _get_meta_description(page)
            clickable_elements = await _extract_clickable_elements(page)
            page_content = await _extract_page_content(page)
            trimmed_content = _trim_text(page_content)

            dom_info = {
                "title": title,
                "url": url,
                "meta_description": meta_description,
                "clickable_elements": clickable_elements,
                "page_content": trimmed_content,
            }

            return _format_dom_info(dom_info)
    except Exception as e:
        return f"[dom 추출 실패] {e}"


async def _get_meta_description(page: Page) -> str:
    """페이지의 meta description을 추출한다.

    Args:
        page: 메타 정보를 추출할 Playwright 페이지 객체

    Returns:
        meta name="description"의 content 속성값. 없으면 빈 문자열.
    """
    try:
        description = await page.evaluate("""() => {
            const meta = document.querySelector('meta[name="description"]');
            return meta ? meta.getAttribute('content') : '';
        }""")
        return description or ""
    except Exception:
        return ""


async def _extract_clickable_elements(page: Page) -> list[dict[str, Any]]:
    """클릭 가능한 요소들을 추출한다.

    button, a[href], input, select, textarea, [role='button'], [onclick]
    선택자에 해당하는 보이는 요소들을 추출하며, 최대 MAX_CLICKABLE_ELEMENTS개까지만 반환한다.

    Args:
        page: 요소를 추출할 Playwright 페이지 객체

    Returns:
        요소 정보 딕셔너리 리스트. 각 딕셔너리는 tag, text, type, placeholder, href, visible 포함.
    """
    try:
        elements: list[dict[str, Any]] = await page.evaluate("""() => {
            const MAX_ELEMENTS = """ + str(MAX_CLICKABLE_ELEMENTS) + """;
            const results = [];
            const seen = new Set();
            const selectors = [
                'button',
                'a[href]',
                'input',
                'select',
                'textarea',
                '[role="button"]',
                '[onclick]'
            ];

            function getTextContent(el) {
                const text = el.innerText || el.textContent || '';
                return text.trim().slice(0, 50);
            }

            for (const selector of selectors) {
                if (results.length >= MAX_ELEMENTS) break;
                document.querySelectorAll(selector).forEach(el => {
                    if (results.length >= MAX_ELEMENTS) return;
                    if (seen.has(el)) return;
                    seen.add(el);

                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.height > 0 && rect.width > 0 &&
                                     window.getComputedStyle(el).display !== 'none';

                    if (!isVisible) return;

                    const info = {
                        tag: el.tagName.toLowerCase(),
                        text: getTextContent(el),
                        type: el.type || null,
                        placeholder: el.placeholder || null,
                        href: el.href || null,
                        visible: true
                    };
                    results.push(info);
                });
            }

            return results.slice(0, MAX_ELEMENTS);
        }""")
        return elements
    except Exception:
        return []


async def _extract_page_content(page: Page) -> str:
    """페이지의 본문 텍스트 내용을 추출한다.

    헤딩, 단락, 리스트, 테이블, 라벨 등의 텍스트를 중복 제거하여 수집한다.

    Args:
        page: 콘텐츠를 추출할 Playwright 페이지 객체

    Returns:
        추출된 본문 텍스트 문자열. 실패 시 빈 문자열.
    """
    try:
        content: str = await page.evaluate("""() => {
            const MAX_TEXT_LEN = 500;
            const seen = new Set();
            const results = [];

            function addText(text) {
                const trimmed = text.trim();
                if (!trimmed || trimmed.length >= MAX_TEXT_LEN || seen.has(trimmed)) {
                    return;
                }
                seen.add(trimmed);
                results.push(trimmed);
            }

            // 헤딩
            document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
                addText(el.innerText);
            });

            // 본문 텍스트
            document.querySelectorAll('p, li, td, th, label, span, div').forEach(el => {
                if (el.innerText && el.children.length === 0) {
                    addText(el.innerText);
                }
            });

            return results.join('\\n');
        }""")
        return content or ""
    except Exception:
        return ""


def _trim_text(text: str, max_chars: int = MAX_CHARS) -> str:
    """텍스트 길이를 제한하고 중간 부분을 생략 표시한다.

    최대 문자 수를 초과하는 경우, 앞부분(60%) + 뒷부분(40%)을 유지하고
    중간에 "[중략]" 표시를 삽입한다.

    Args:
        text: 원본 텍스트 문자열
        max_chars: 최대 허용 문자 수. 기본값 8000.

    Returns:
        제한된 길이의 텍스트 문자열.
    """
    if len(text) <= max_chars:
        return text

    head_size = int(max_chars * 0.6)
    tail_size = int(max_chars * 0.4)

    head = text[:head_size]
    tail = text[-tail_size:]

    return f"{head}\n...[중략]...\n{tail}"


def _format_dom_info(dom_info: dict[str, Any]) -> str:
    """구조화된 DOM 정보를 포맷된 문자열로 변환한다.

    Args:
        dom_info: title, url, meta_description, clickable_elements, page_content 포함 딕셔너리

    Returns:
        포맷된 DOM 정보 문자열.
    """
    sections = []

    # [Page Info] 섹션
    sections.append("[Page Info]")
    sections.append(f"Title: {dom_info.get('title', 'N/A')}")
    sections.append(f"URL: {dom_info.get('url', 'N/A')}")
    if dom_info.get("meta_description"):
        sections.append(f"Description: {dom_info['meta_description']}")
    sections.append("")

    # [Clickable Elements] 섹션
    sections.append("[Clickable Elements]")
    clickable = dom_info.get("clickable_elements", [])
    if clickable:
        for idx, elem in enumerate(clickable, 1):
            tag = elem.get("tag", "unknown")
            text = elem.get("text", "")
            elem_type = elem.get("type")
            placeholder = elem.get("placeholder")
            href = elem.get("href")

            # 요소 설명 구성
            parts = [f"[{tag}]"]
            if text:
                parts.append(text)
            if elem_type:
                parts.append(f"type={elem_type}")
            if placeholder:
                parts.append(f"placeholder={placeholder}")
            if href:
                parts.append(f"→ {href}")

            sections.append(f"{idx}. {' '.join(parts)}")
    else:
        sections.append("(No clickable elements found)")
    sections.append("")

    # [Page Content] 섹션
    sections.append("[Page Content]")
    sections.append(dom_info.get("page_content", "(No content found)"))

    return "\n".join(sections)
