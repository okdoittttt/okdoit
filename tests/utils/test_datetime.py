"""core.utils.datetime 단위 테스트."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from core.utils.datetime import (
    DEFAULT_TIMEZONE,
    format_kr_date,
    now,
    today,
    tomorrow,
    weekday_kr,
)


class TestToday:
    """today() 함수 테스트."""

    def test_ref가_주어지면_해당_날짜를_반환한다(self) -> None:
        ref = datetime(2026, 4, 24, 15, 30, tzinfo=ZoneInfo("Asia/Seoul"))
        assert today(ref=ref) == date(2026, 4, 24)

    def test_타임존이_날짜_경계를_넘기면_로컬_날짜를_따른다(self) -> None:
        # UTC 기준 2026-04-24 20:00 == Seoul 기준 2026-04-25 05:00
        ref_utc = datetime(2026, 4, 24, 20, 0, tzinfo=ZoneInfo("UTC"))
        assert today(tz="Asia/Seoul", ref=ref_utc) == date(2026, 4, 25)
        assert today(tz="UTC", ref=ref_utc) == date(2026, 4, 24)


class TestTomorrow:
    """tomorrow() 함수 테스트."""

    def test_내일은_오늘에서_하루_뒤다(self) -> None:
        ref = datetime(2026, 4, 24, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        assert tomorrow(ref=ref) == date(2026, 4, 25)

    def test_월말에서_다음_달로_넘어간다(self) -> None:
        ref = datetime(2026, 4, 30, 23, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        assert tomorrow(ref=ref) == date(2026, 5, 1)

    def test_연말에서_다음_해로_넘어간다(self) -> None:
        ref = datetime(2026, 12, 31, 23, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        assert tomorrow(ref=ref) == date(2027, 1, 1)


class TestWeekdayKr:
    """weekday_kr() 함수 테스트."""

    def test_각_요일을_한글로_반환한다(self) -> None:
        # 2026-04-20(월) ~ 2026-04-26(일)
        expected = ["월", "화", "수", "목", "금", "토", "일"]
        for i, kr in enumerate(expected):
            assert weekday_kr(date(2026, 4, 20 + i)) == kr


class TestFormatKrDate:
    """format_kr_date() 함수 테스트."""

    def test_금요일_형식을_확인한다(self) -> None:
        assert format_kr_date(date(2026, 4, 24)) == "2026-04-24 (금)"

    def test_월요일_형식을_확인한다(self) -> None:
        assert format_kr_date(date(2026, 4, 20)) == "2026-04-20 (월)"


class TestNow:
    """now() 함수 테스트."""

    def test_기본_타임존은_아시아_서울이다(self) -> None:
        result = now()
        assert result.tzinfo is not None
        assert str(result.tzinfo) == DEFAULT_TIMEZONE

    def test_명시적_타임존을_사용한다(self) -> None:
        result = now(tz="UTC")
        assert str(result.tzinfo) == "UTC"
