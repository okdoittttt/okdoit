"""observe 노드 - DOM 관찰 및 인덱싱.

브라우저 내부에서 JS 인젝션으로 상호작용 가능한 요소를 선별하고, 각 요소에
``data-oi-idx`` 속성을 부여해 인덱스 기반 액션(click_index, type_index 등)이
안정적으로 참조하도록 한다.

파이프라인:
    1. 이전 턴의 ``data-oi-idx`` 속성 제거
    2. 후보 셀렉터로 상호작용 요소 수집
    3. 가시성 필터 (display/visibility/opacity, bbox 크기)
    4. 뷰포트 교차 필터 (완전히 밖인 요소는 제외)
    5. Paint order hit-test (가려진 요소 제거)
    6. 부모-자식 99% 포함 중복 제거
    7. 최대 MAX_INTERACTIVE_ELEMENTS 컷오프, 인덱스 부여
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup
from langsmith import trace as ls_trace
from markdownify import markdownify as md
from playwright.async_api import Page

from core.browser import BrowserManager
from core.state import AgentState, ElementInfo

# 프롬프트에 노출할 상호작용 요소 최대 개수.
MAX_INTERACTIVE_ELEMENTS = 120
# Markdown 본문 토큰 예산 (1 토큰 ≈ 4자 근사).
TOKEN_BUDGET = 2000


async def observe(state: AgentState) -> AgentState:
    """현재 브라우저 상태를 관찰하고 state를 업데이트한다.

    The Loop의 첫 번째 노드. 스크린샷, 구조화된 DOM 정보, 인덱싱된 상호작용 요소
    맵을 수집해 state에 기록한다. 인덱스 기반 액션(click_index 등)은 브라우저
    DOM에 심긴 ``data-oi-idx`` 속성을 통해 요소를 참조한다.

    Args:
        state: 현재 에이전트 상태.

    Returns:
        screenshot_path, dom_text, current_url, selector_map이 업데이트된
        AgentState. 에러 발생 시 error 필드에 메시지를 기록하고 반환한다.
    """
    try:
        manager = BrowserManager()
        page = await manager.get_page()

        filename = f"step_{state['iterations']}.png"
        screenshot_path = await manager.take_screenshot(filename)

        elements, dom_text = await _extract_structured_dom(page)
        current_url = page.url
        selector_map: dict[int, ElementInfo] = {e["index"]: e for e in elements}

        return {
            **state,
            "screenshot_path": screenshot_path,
            "dom_text": dom_text,
            "current_url": current_url,
            "selector_map": selector_map,
            "iterations": state["iterations"] + 1,
            "error": None,
        }
    except RuntimeError as e:
        return {**state, "error": f"[observe] Browser not ready: {e}"}
    except Exception as e:
        return {**state, "error": f"[observe] Unexpected error: {e}"}


async def _extract_structured_dom(page: Page) -> tuple[list[ElementInfo], str]:
    """페이지에서 인덱싱된 상호작용 요소와 포맷된 DOM 텍스트를 추출한다.

    Args:
        page: Playwright 페이지.

    Returns:
        (ElementInfo 리스트, LLM 입력용 포맷 문자열) 튜플.
        추출 실패 시 ([], 에러 메시지) 반환.
    """
    try:
        url = page.url
        with ls_trace(
            name="browser_extract_dom",
            inputs={"url": url},
            tags=["browser", "observe"],
        ):
            metadata = await _get_page_metadata(page)
            elements = await _collect_interactive_elements(page)
            content = await _extract_main_content(page)
            budgeted = _apply_token_budget(content)
            return elements, _format_observation(metadata, elements, budgeted)
    except Exception as e:
        return [], f"[dom 추출 실패] {e}"


async def _get_page_metadata(page: Page) -> dict[str, str]:
    """페이지의 title, url, meta description을 반환한다.

    Args:
        page: Playwright 페이지.

    Returns:
        title, url, description 키의 딕셔너리. description이 없으면 빈 문자열.
    """
    title = await page.title()
    url = page.url
    try:
        meta = await page.query_selector('meta[name="description"]')
        description = (await meta.get_attribute("content") or "") if meta else ""
    except Exception:
        description = ""
    return {"title": title, "url": url, "description": description}


async def _collect_interactive_elements(page: Page) -> list[ElementInfo]:
    """브라우저 내에서 상호작용 요소를 필터링하고 인덱스를 부여한다.

    단일 ``page.evaluate`` 호출로 수집·필터링·인덱스 부여를 끝낸다.
    각 요소에 ``data-oi-idx`` 속성을 심어서 이후 인덱스 기반 액션이 locator를
    직접 만들 수 있게 한다.

    실패 시 예외를 삼키지 않고 빈 리스트로 폴백한다(테스트/에지 케이스 안정성).

    Args:
        page: Playwright 페이지.

    Returns:
        ElementInfo 리스트. 순서는 브라우저의 DOM 순서를 따른다.
    """
    try:
        raw: list[dict[str, Any]] = await page.evaluate(
            _INTERACTIVE_ELEMENTS_SCRIPT,
            MAX_INTERACTIVE_ELEMENTS,
        )
    except Exception:
        return []

    elements: list[ElementInfo] = []
    for item in raw:
        try:
            elements.append(
                ElementInfo(
                    index=int(item["index"]),
                    tag=str(item["tag"]),
                    role=item.get("role"),
                    text=str(item.get("text") or "")[:100],
                    attributes={
                        str(k): str(v)
                        for k, v in (item.get("attributes") or {}).items()
                        if v is not None
                    },
                    bbox=[float(x) for x in (item.get("bbox") or [0.0, 0.0, 0.0, 0.0])],
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return elements


async def _extract_main_content(page: Page) -> str:
    """HTML에서 노이즈를 제거한 뒤 Markdown으로 변환하여 반환한다.

    script/style/nav/footer 등 노이즈 태그와 광고/메뉴 클래스를 제거한 후
    main > article > body 순으로 추출하여 Markdown으로 변환한다.

    Args:
        page: Playwright 페이지.

    Returns:
        Markdown 본문. 실패 시 빈 문자열.
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

    1 토큰 ≈ 4글자 근사식을 사용한다.

    Args:
        text: 원본 텍스트.
        max_tokens: 최대 허용 토큰 수. 기본 2000.

    Returns:
        제한된 텍스트.
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(이하 생략됨)"


def _format_observation(
    metadata: dict[str, str],
    elements: list[ElementInfo],
    content: str,
) -> str:
    """관찰 결과를 LLM 입력용 포맷 문자열로 변환한다.

    세 섹션으로 구성된다.
        [Page Info]: title, url, description
        [Interactive Elements]: ``[idx]<tag attrs>text</tag>`` 한 줄씩
        [Page Content]: Markdown 본문 (토큰 예산 적용됨)

    Args:
        metadata: ``_get_page_metadata`` 결과.
        elements: ``_collect_interactive_elements`` 결과.
        content: ``_extract_main_content`` + ``_apply_token_budget`` 결과.

    Returns:
        포맷된 문자열.
    """
    sections: list[str] = []

    sections.append("[Page Info]")
    sections.append(f"Title: {metadata.get('title', 'N/A')}")
    sections.append(f"URL: {metadata.get('url', 'N/A')}")
    if metadata.get("description"):
        sections.append(f"Description: {metadata['description']}")
    sections.append("")

    sections.append("[Interactive Elements]")
    if elements:
        for elem in elements:
            sections.append(_format_element_line(elem))
    else:
        sections.append("(상호작용 가능한 요소 없음)")
    sections.append("")

    sections.append("[Page Content]")
    sections.append(content or "(No content found)")

    return "\n".join(sections)


def _format_element_line(elem: ElementInfo) -> str:
    """ElementInfo 하나를 LLM 프롬프트에 실릴 한 줄로 포맷한다.

    포맷 예:
        [0]<a href="/login">로그인</a>
        [1]<input placeholder="이메일" type="email" />
        [2]<button>확인</button>
        [5]<input type="checkbox" aria-label="약관 동의" />

    Args:
        elem: 단일 요소 정보.

    Returns:
        한 줄 문자열.
    """
    idx = elem["index"]
    tag = elem["tag"]
    text = elem.get("text", "")
    attrs = elem.get("attributes", {})

    # 프롬프트에 우선 노출할 속성 키 순서. 없으면 생략.
    preferred_keys = ("type", "href", "name", "value", "placeholder", "aria-label", "title", "alt", "role")
    attr_parts: list[str] = []
    for k in preferred_keys:
        v = attrs.get(k)
        if v:
            # 따옴표 이스케이프 (텍스트 안의 " 만 처리)
            safe = v.replace('"', '\\"')
            attr_parts.append(f'{k}="{safe}"')

    attr_str = (" " + " ".join(attr_parts)) if attr_parts else ""

    # 내용 있는 요소는 <tag ...>text</tag>, 자기완결 요소는 <tag ... />
    void_tags = {"input", "img", "br", "hr", "meta", "link"}
    if tag in void_tags or not text:
        return f"[{idx}]<{tag}{attr_str} />"
    # 긴 텍스트는 요소 포맷에서도 잘라줌 (line noise 방지)
    short_text = text if len(text) <= 80 else text[:79] + "…"
    return f"[{idx}]<{tag}{attr_str}>{short_text}</{tag}>"


# JS 인젝션 스크립트.
#
# - 인자: maxN (정수)
# - 반환: [{index, tag, role, text, attributes, bbox}] 배열
#
# 알고리즘:
#   1. 이전 턴의 data-oi-idx 속성 전부 제거 → 이번 턴에 새로 부여
#   2. 후보 셀렉터로 element 수집 (+ 중복 제거)
#   3. 가시성 필터 (display/visibility/opacity, bbox 크기)
#   4. 뷰포트 완전 밖 요소 제외 (조금 걸친 건 유지, 스크롤 후보)
#   5. Paint order: 중심점 hit-test로 다른 요소에 완전히 가려진 것 제거
#      (viewport 밖 중심은 hit-test가 무의미하므로 건너뜀 — 스크롤 후보 보존)
#   6. 부모-자식 99% 포함 관계에서 부모 제거 → 더 구체적인 자식 우선
#   7. 상위 maxN개 컷오프, data-oi-idx 부여
_INTERACTIVE_ELEMENTS_SCRIPT = r"""
(maxN) => {
  document.querySelectorAll('[data-oi-idx]').forEach(el => el.removeAttribute('data-oi-idx'));

  const CANDIDATE = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    '[role="button"]',
    '[role="link"]',
    '[role="checkbox"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[role="option"]',
    '[contenteditable=""]',
    '[contenteditable="true"]',
    '[onclick]',
    '[tabindex]:not([tabindex="-1"])'
  ].join(', ');

  const raw = Array.from(new Set(document.querySelectorAll(CANDIDATE)));
  const viewW = window.innerWidth;
  const viewH = window.innerHeight;

  // 1) 가시성 + 뷰포트 교차 필터
  const visible = [];
  for (const el of raw) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity || '1') === 0) continue;
    // 완전히 뷰포트 밖이면 제외 (약간 걸친 건 유지)
    if (r.bottom < -50 || r.top > viewH + 200 || r.right < -50 || r.left > viewW + 50) continue;
    visible.push({ el, rect: r });
  }

  // 2) Paint order hit-test (가려진 요소 제거)
  const painted = [];
  for (const entry of visible) {
    const { el, rect } = entry;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    // 중심이 뷰포트 밖이면 hit-test 무의미 → 통과
    if (cx < 0 || cx > viewW || cy < 0 || cy > viewH) {
      painted.push(entry);
      continue;
    }
    const top = document.elementFromPoint(cx, cy);
    if (!top) { painted.push(entry); continue; }
    // 자기 자신이거나 자기를 감싸는 부모면 OK
    if (el === top || el.contains(top) || top.contains(el)) {
      painted.push(entry);
    }
  }

  // 3) 부모-자식 99% 포함 중복 제거 (더 구체적인 자식 우선)
  const kept = new Set(painted.map(e => e.el));
  for (const entry of painted) {
    let p = entry.el.parentElement;
    const cRect = entry.rect;
    const childArea = cRect.width * cRect.height;
    if (childArea <= 0) continue;
    while (p) {
      if (kept.has(p)) {
        const pRect = p.getBoundingClientRect();
        const ix = Math.max(0, Math.min(cRect.right, pRect.right) - Math.max(cRect.left, pRect.left));
        const iy = Math.max(0, Math.min(cRect.bottom, pRect.bottom) - Math.max(cRect.top, pRect.top));
        const intersect = ix * iy;
        if (intersect / childArea >= 0.99) {
          kept.delete(p);
        }
      }
      p = p.parentElement;
    }
  }

  // 4) 최종 선별 + 인덱스 부여
  const finalList = painted.filter(e => kept.has(e.el)).slice(0, maxN);
  const ATTR_KEYS = ['type', 'name', 'value', 'placeholder', 'aria-label', 'title', 'alt', 'href', 'role'];
  const results = [];

  finalList.forEach((entry, idx) => {
    const { el, rect } = entry;
    el.setAttribute('data-oi-idx', String(idx));

    let text = (el.innerText || el.textContent || '').trim();
    text = text.replace(/\s+/g, ' ').slice(0, 100);

    const attrs = {};
    for (const an of ATTR_KEYS) {
      const av = el.getAttribute(an);
      if (av != null && av !== '') attrs[an] = String(av).slice(0, 100);
    }
    // input type 보강: getAttribute는 명시적 type만 돌려주므로 prop도 참조
    if (el.tagName.toLowerCase() === 'input' && !attrs.type && el.type) {
      attrs.type = el.type;
    }

    results.push({
      index: idx,
      tag: el.tagName.toLowerCase(),
      role: attrs.role || null,
      text,
      attributes: attrs,
      bbox: [rect.left, rect.top, rect.width, rect.height],
    });
  });

  return results;
}
"""
