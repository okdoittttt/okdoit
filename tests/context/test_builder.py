"""core.context.builder 단위 테스트."""

from datetime import datetime
from zoneinfo import ZoneInfo

from core.context.builder import build_runtime_context, format_runtime_context_block


REF_2026_04_24_SEOUL = datetime(2026, 4, 24, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))


class TestBuildRuntimeContext:
    """build_runtime_context() 테스트."""

    def test_오늘_내일_타임존_키를_포함한다(self) -> None:
        ctx = build_runtime_context(ref=REF_2026_04_24_SEOUL)
        assert ctx == {
            "today": "2026-04-24 (금)",
            "tomorrow": "2026-04-25 (토)",
            "timezone": "Asia/Seoul",
        }

    def test_타임존이_바뀌면_기록된_타임존도_바뀐다(self) -> None:
        ctx = build_runtime_context(tz="UTC", ref=REF_2026_04_24_SEOUL)
        assert ctx["timezone"] == "UTC"


class TestFormatRuntimeContextBlock:
    """format_runtime_context_block() 테스트."""

    def test_헤더와_세_항목을_포함한다(self) -> None:
        block = format_runtime_context_block(ref=REF_2026_04_24_SEOUL)
        assert block == (
            "[실행 컨텍스트]\n"
            "- 오늘: 2026-04-24 (금)\n"
            "- 내일: 2026-04-25 (토)\n"
            "- 타임존: Asia/Seoul"
        )

    def test_ref가_없어도_블록이_정상_생성된다(self) -> None:
        # 현재 시각으로 동작하는지만 확인 (값 단정 없이 구조만 검증)
        block = format_runtime_context_block()
        assert block.startswith("[실행 컨텍스트]")
        assert "- 오늘:" in block
        assert "- 내일:" in block
        assert "- 타임존:" in block
