from typing import Any

from bs4 import BeautifulSoup
from langsmith import trace as ls_trace
from markdownify import markdownify as md
from playwright.async_api import Page

from core.browser import BrowserManager
from core.state import AgentState

MAX_ELEMENTS = 50
TOKEN_BUDGET = 2000


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

    메타데이터, 클릭 가능한 요소, Markdown으로 변환된 본문을 수집하여
    LLM이 이해하기 쉬운 형식으로 반환한다.

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
            metadata = await _get_page_metadata(page)
            elements = await _extract_clickable_elements(page)
            content = await _extract_main_content(page)
            budgeted_content = _apply_token_budget(content)
            return _format_observation(metadata, elements, budgeted_content)
    except Exception as e:
        return f"[dom 추출 실패] {e}"


async def _get_page_metadata(page: Page) -> dict[str, str]:
    """페이지의 title, url, meta description을 반환한다.

    Args:
        page: 메타 정보를 추출할 Playwright 페이지 객체

    Returns:
        title, url, description 키를 포함한 딕셔너리.
        description이 없으면 빈 문자열.
    """
    title = await page.title()
    url = page.url
    try:
        description = await page.get_attribute('meta[name="description"]', "content") or ""
    except Exception:
        description = ""
    return {"title": title, "url": url, "description": description}


async def _extract_clickable_elements(page: Page) -> list[dict[str, Any]]:
    """클릭 가능한 인터랙티브 요소들을 추출한다.

    화면에 보이는 button, a[href], input, select, textarea, role=button/link,
    onclick 요소를 대상으로 하며 중복을 제거하고 최대 MAX_ELEMENTS개까지 반환한다.

    Args:
        page: 요소를 추출할 Playwright 페이지 객체

    Returns:
        index, tag, type, text, placeholder, href, name, aria_label을 담은
        딕셔너리 리스트.
    """
    try:
        elements: list[dict[str, Any]] = await page.evaluate(f"""() => {{
            const MAX_ELEMENTS = {MAX_ELEMENTS};
            const results = [];
            const seen = new Set();
            const selectors = [
                'button:not([disabled])',
                'a[href]',
                'input:not([type="hidden"])',
                'select',
                'textarea',
                '[role="button"]',
                '[role="link"]',
                '[onclick]'
            ];

            let index = 1;
            for (const selector of selectors) {{
                if (results.length >= MAX_ELEMENTS) break;
                document.querySelectorAll(selector).forEach(el => {{
                    if (results.length >= MAX_ELEMENTS) return;
                    if (seen.has(el)) return;
                    seen.add(el);

                    if (el.offsetParent === null) return;
                    const rect = el.getBoundingClientRect();
                    if (rect.width <= 0) return;

                    results.push({{
                        index: index++,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || null,
                        text: el.innerText?.trim().slice(0, 80) || null,
                        placeholder: el.placeholder || null,
                        href: el.href || null,
                        name: el.name || null,
                        aria_label: el.getAttribute('aria-label') || null
                    }});
                }});
            }}

            return results;
        }}""")
        return elements
    except Exception:
        return []


async def _extract_main_content(page: Page) -> str:
    """HTML에서 노이즈를 제거한 뒤 Markdown으로 변환하여 반환한다.

    script/style/nav/footer 등 노이즈 태그와 광고/메뉴 클래스를 제거한 후
    main > article > body 순으로 우선 추출하여 Markdown으로 변환한다.

    Args:
        page: 콘텐츠를 추출할 Playwright 페이지 객체

    Returns:
        Markdown으로 변환된 본문 문자열. 실패 시 빈 문자열.
    """
    try:
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        remove_tags = [
            "script", "style", "noscript", "head",
            "nav", "footer", "aside", "iframe", "svg",
        ]
        for tag in remove_tags:
            for el in soup.find_all(tag):
                el.decompose()

        remove_classes = [
            "ad", "advertisement", "banner", "cookie",
            "popup", "modal", "sidebar", "menu", "navbar",
        ]
        for cls in remove_classes:
            for el in soup.find_all(class_=lambda c: c and cls in c.lower()):
                el.decompose()

        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main is None:
            return ""

        markdown = md(str(main), heading_style="ATX", bullets="-")
        lines = [line for line in markdown.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception:
        return ""


def _apply_token_budget(text: str, max_tokens: int = TOKEN_BUDGET) -> str:
    """텍스트를 토큰 예산 내로 제한한다.

    1 토큰 ≈ 4글자 근사식을 사용하여 초과 시 앞부분을 유지하고 생략 표시를 추가한다.

    Args:
        text: 원본 텍스트 문자열
        max_tokens: 최대 허용 토큰 수. 기본값 2000.

    Returns:
        제한된 텍스트 문자열.
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(이하 생략됨)"


def _format_observation(
    metadata: dict[str, str],
    elements: list[dict[str, Any]],
    content: str,
) -> str:
    """관찰 결과를 LLM 입력용 포맷 문자열로 변환한다.

    Args:
        metadata: title, url, description을 담은 딕셔너리
        elements: 클릭 가능한 요소 딕셔너리 리스트
        content: 토큰 예산이 적용된 Markdown 본문

    Returns:
        [Page Info] / [Clickable Elements] / [Page Content] 섹션으로 구성된 문자열.
    """
    sections: list[str] = []

    sections.append("[Page Info]")
    sections.append(f"Title: {metadata.get('title', 'N/A')}")
    sections.append(f"URL: {metadata.get('url', 'N/A')}")
    if metadata.get("description"):
        sections.append(f"Description: {metadata['description']}")
    sections.append("")

    sections.append("[Clickable Elements]")
    if elements:
        for elem in elements:
            tag = elem.get("tag", "unknown")
            elem_type = elem.get("type")
            text = elem.get("text") or ""
            placeholder = elem.get("placeholder")
            href = elem.get("href")
            aria_label = elem.get("aria_label")

            tag_str = f"[{tag}/{elem_type}]" if elem_type else f"[{tag}]"
            display_text = text if text else (aria_label or "")

            parts = [tag_str]
            if display_text:
                parts.append(display_text)
            if placeholder:
                parts.append(f'placeholder="{placeholder}"')
            if href:
                parts.append(f"→ {href}")

            sections.append(" ".join(parts))
    else:
        sections.append("(No clickable elements found)")
    sections.append("")

    sections.append("[Page Content]")
    sections.append(content or "(No content found)")

    return "\n".join(sections)
