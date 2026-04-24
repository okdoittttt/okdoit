"""런타임 컨텍스트 빌더.

LLM이 코드에서 계산해야만 알 수 있는 값(오늘 날짜, 타임존 등)을
수집해 프롬프트에 주입 가능한 형태로 반환한다.

앞으로 사용자 로케일, 세션 메타, 실행 환경 정보 등도 이 모듈에 추가한다.
"""

from __future__ import annotations

from datetime import datetime

from core.utils.datetime import (
    DEFAULT_TIMEZONE,
    format_kr_date,
    today,
    tomorrow,
)


def build_runtime_context(
    tz: str = DEFAULT_TIMEZONE,
    ref: datetime | None = None,
) -> dict[str, str]:
    """LLM 프롬프트에 주입할 런타임 컨텍스트 dict를 생성한다.

    Args:
        tz: IANA 타임존 이름.
        ref: 기준 시각. ``None``이면 현재 시각을 사용한다. 테스트에서 고정 시각을 주입할 때 사용한다.

    Returns:
        다음 키를 포함한 dict:
            - ``today``: ``"2026-04-24 (금)"``
            - ``tomorrow``: ``"2026-04-25 (토)"``
            - ``timezone``: ``tz`` 값 그대로
    """
    today_date = today(tz=tz, ref=ref)
    tomorrow_date = tomorrow(tz=tz, ref=ref)
    return {
        "today": format_kr_date(today_date),
        "tomorrow": format_kr_date(tomorrow_date),
        "timezone": tz,
    }


def format_runtime_context_block(
    tz: str = DEFAULT_TIMEZONE,
    ref: datetime | None = None,
) -> str:
    """런타임 컨텍스트를 프롬프트에 바로 삽입할 수 있는 텍스트 블록으로 포맷한다.

    Args:
        tz: IANA 타임존 이름.
        ref: 기준 시각. ``None``이면 현재 시각을 사용한다.

    Returns:
        ``[실행 컨텍스트]`` 헤더를 포함한 여러 줄 텍스트. 예::

            [실행 컨텍스트]
            - 오늘: 2026-04-24 (금)
            - 내일: 2026-04-25 (토)
            - 타임존: Asia/Seoul
    """
    ctx = build_runtime_context(tz=tz, ref=ref)
    return (
        "[실행 컨텍스트]\n"
        f"- 오늘: {ctx['today']}\n"
        f"- 내일: {ctx['tomorrow']}\n"
        f"- 타임존: {ctx['timezone']}"
    )
