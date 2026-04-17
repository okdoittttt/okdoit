"""네이버 금융 페이지에서 observe 결과를 출력하는 샘플 스크립트."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.browser import BrowserManager
from core.nodes.observe import (
    _apply_token_budget,
    _extract_clickable_elements,
    _extract_main_content,
    _format_observation,
    _get_page_metadata,
)

TARGET_URL = "https://finance.naver.com/"


async def main() -> None:
    """observe 파이프라인을 실행하고 dom_text 결과를 출력한다."""
    manager = BrowserManager(headless=True)
    await manager.start()
    try:
        page = await manager.get_page()
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=15000)

        print(f"[페이지 로드 완료] {page.url}\n")
        print("=" * 60)

        metadata = await _get_page_metadata(page)
        elements = await _extract_clickable_elements(page)
        content = await _extract_main_content(page)
        budgeted = _apply_token_budget(content)

        dom_text = _format_observation(metadata, elements, budgeted)
        print(dom_text)

        print("\n" + "=" * 60)
        print(f"[통계]")
        print(f"  클릭 가능 요소: {len(elements)}개")
        print(f"  Page Content 길이: {len(budgeted)}자 (토큰 약 {len(budgeted)//4})")
        print(f"  전체 dom_text 길이: {len(dom_text)}자")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
