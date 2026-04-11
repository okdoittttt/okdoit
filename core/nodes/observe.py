from playwright.async_api import Page

from core.browser import BrowserManager
from core.state import AgentState


async def observe(state: AgentState) -> AgentState:
    """현재 브라우저 상태를 관찰하고 state를 업데이트한다.

    The Loop의 첫 번째 노드. 스크린샷 촬영, DOM 텍스트 추출, 현재 URL을 수집해
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

        dom_text = await _extract_dom_text(page)
        current_url = page.url

        return {
            **state,
            "screenshot_path": screenshot_path,
            "dom_text": dom_text,
            "current_url": current_url,
            "error": None,
        }
    except RuntimeError as e:
        return {**state, "error": f"[observe] Browser not ready: {e}"}
    except Exception as e:
        return {**state, "error": f"[observe] Unexpected error: {e}"}


async def _extract_dom_text(page: Page) -> str:
    """페이지에서 LLM에 전달할 텍스트를 추출한다.

    JavaScript를 통해 DOM을 읽기 전용으로 순회하며 헤딩, 본문, 링크,
    인터랙티브 요소를 수집한다. 원본 DOM은 수정하지 않는다.

    Args:
        page: 텍스트를 추출할 Playwright 페이지 객체

    Returns:
        중복 제거된 DOM 텍스트. 추출 실패 시 에러 메시지를 반환한다.
    """
    try:
        lines: list[str] = await page.evaluate("""() => {
            const MAX_LEN = 500;
            const seen = new Set();
            const results = [];

            function add(text) {
                const t = text.trim();
                if (!t || t.length >= MAX_LEN || seen.has(t)) return;
                seen.add(t);
                results.push(t);
            }

            // 헤딩
            document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
                add(el.innerText);
            });

            // 본문 텍스트
            document.querySelectorAll('p, li, td, th, label').forEach(el => {
                add(el.innerText);
            });

            // 링크
            document.querySelectorAll('a[href]').forEach(el => {
                const text = el.innerText.trim();
                const href = el.getAttribute('href');
                if (text && href) add(`[링크] ${text} → ${href}`);
            });

            // 인터랙티브 요소
            document.querySelectorAll('button, input, textarea, select').forEach(el => {
                const label =
                    el.getAttribute('aria-label') ||
                    el.getAttribute('placeholder') ||
                    el.innerText ||
                    el.getAttribute('name') ||
                    '';
                if (label.trim()) add(`[입력] ${label.trim()}`);
            });

            return results;
        }""")
        return "\n".join(lines)
    except Exception as e:
        return f"[dom 추출 실패] {e}"
