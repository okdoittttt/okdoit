"""테스트 공용 fixture 모음.

local-first 리팩토링(PR2~) 부터 사용하는 ``OKDOIT_DATA_DIR`` + ``get_settings``
캐시 격리 fixture 를 제공한다. opt-in 방식 — 기존 단위 테스트에는 영향 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from server.internal.config import get_settings


@pytest.fixture
def isolated_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """``OKDOIT_DATA_DIR`` 를 tmp_path 로 격리하고 ``get_settings`` 캐시를 비운다.

    DB 부트스트랩이나 ``settings.db_path`` / ``settings.screenshot_dir`` 를 거치는
    테스트에서 사용. ``get_settings`` 가 ``lru_cache(maxsize=1)`` 라 다른 테스트가
    먼저 호출했으면 굳어버린 ``data_dir`` 를 쓸 수 있어 명시적으로 cache_clear 한다.

    Yields:
        ``tmp_path`` 그대로 — 테스트 측이 sub-path 를 만들고 검증할 때 쓴다.
    """
    monkeypatch.setenv("OKDOIT_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        yield tmp_path
    finally:
        # 다른 테스트가 영향을 받지 않도록 캐시를 다시 비운다 — 다음 호출에서
        # monkeypatch 가 되돌린 환경변수가 반영된다.
        get_settings.cache_clear()
