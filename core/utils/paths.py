"""PyInstaller frozen / dev 환경 모두에서 동작하는 리소스 경로 헬퍼.

dev 모드에선 ``Path(__file__).parent...`` 로 프로젝트 루트를 추정할 수 있지만,
PyInstaller 로 묶인 frozen 모드에선 ``__file__`` 의 의미가 달라 깨진다. 게다가
프로젝트 루트의 ``prompt/`` 같은 데이터 파일은 PyInstaller 가 자동 collect 하지
않아 ``--add-data`` 로 명시 포함 시 ``sys._MEIPASS`` 아래에 풀린다.

이 모듈의 ``resource_path`` 는 두 환경의 차이를 흡수해서 호출 측이 동일한
방식으로 데이터 파일을 읽을 수 있게 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """프로젝트 데이터 파일 경로를 dev / PyInstaller frozen 모두에서 동일하게 푼다.

    frozen 모드(``sys.frozen=True`` + ``sys._MEIPASS`` 존재)에선 PyInstaller 가
    풀어둔 ``_MEIPASS`` 디렉토리를 베이스로, dev 모드에선 ``core/`` 의 부모(프로젝트
    루트) 를 베이스로 사용한다.

    Args:
        *parts: 경로 구성 요소. 예: ``resource_path("prompt", "agent.md")``.

    Returns:
        ``Path`` — 호출 측이 ``.read_text()`` / ``.read_bytes()`` 로 바로 사용 가능.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and meipass:
        base = Path(meipass)
    else:
        # core/utils/paths.py → core/utils → core → 프로젝트 루트
        base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(*parts)
