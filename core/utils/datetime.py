"""날짜 및 시간 관련 순수 함수 헬퍼.

LLM 프롬프트에 주입할 "오늘/내일" 같은 런타임 날짜 정보를 계산한다.
테스트 가능성을 위해 모든 함수는 현재 시각을 인자로 받을 수 있다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Seoul"

_KR_WEEKDAYS: tuple[str, ...] = ("월", "화", "수", "목", "금", "토", "일")


def now(tz: str = DEFAULT_TIMEZONE) -> datetime:
    """지정한 타임존의 현재 시각을 반환한다.

    Args:
        tz: IANA 타임존 이름. 기본값은 ``Asia/Seoul``.

    Returns:
        타임존이 부여된 현재 ``datetime`` 객체.
    """
    return datetime.now(ZoneInfo(tz))


def today(tz: str = DEFAULT_TIMEZONE, ref: datetime | None = None) -> date:
    """오늘 날짜를 지정한 타임존 기준으로 반환한다.

    ``ref``가 ``tz``와 다른 타임존을 갖더라도, 반환 날짜는 ``tz`` 기준으로 환산된다.

    Args:
        tz: IANA 타임존 이름.
        ref: 기준 시각(타임존이 부여된 ``datetime``). ``None``이면 현재 시각을 사용한다.

    Returns:
        ``tz`` 로컬 기준 날짜.
    """
    base = ref if ref is not None else now(tz)
    return base.astimezone(ZoneInfo(tz)).date()


def tomorrow(tz: str = DEFAULT_TIMEZONE, ref: datetime | None = None) -> date:
    """내일 날짜를 반환한다.

    Args:
        tz: IANA 타임존 이름.
        ref: 기준 시각. ``None``이면 ``now(tz)``를 사용한다.

    Returns:
        기준 시각 다음 날짜.
    """
    return today(tz=tz, ref=ref) + timedelta(days=1)


def weekday_kr(d: date) -> str:
    """날짜의 한글 요일명(한 글자)을 반환한다.

    Args:
        d: 대상 날짜.

    Returns:
        ``"월"`` ~ ``"일"`` 중 하나.
    """
    return _KR_WEEKDAYS[d.weekday()]


def format_kr_date(d: date) -> str:
    """날짜를 ``"YYYY-MM-DD (요일)"`` 형식으로 포맷한다.

    Args:
        d: 대상 날짜.

    Returns:
        ``"2026-04-24 (금)"`` 형태의 문자열.
    """
    return f"{d.isoformat()} ({weekday_kr(d)})"
