"""``OKDOIT_DATA_DIR`` 가 sidecar 의 모든 파일 I/O 기준점이 되는지 확인.

local-first 리팩토링 PR 1 의 회귀 가드 — sidecar 가 ``settings.data_dir`` 한 곳을
통해서만 디스크에 접근해야 dev / prod / 테스트 환경 분리가 가능하다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.internal.config import ServerSettings


def test_data_dir_default_is_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``OKDOIT_DATA_DIR`` 미지정 시 cwd 가 기본값이 된다."""
    monkeypatch.delenv("OKDOIT_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = ServerSettings()
    assert settings.data_dir == Path.cwd()


def test_data_dir_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``OKDOIT_DATA_DIR`` 환경변수가 있으면 그 경로가 그대로 들어간다."""
    monkeypatch.setenv("OKDOIT_DATA_DIR", str(tmp_path))
    settings = ServerSettings()
    assert settings.data_dir == tmp_path


def test_screenshot_dir_under_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``screenshot_dir`` 는 ``data_dir/screenshots`` 다."""
    monkeypatch.setenv("OKDOIT_DATA_DIR", str(tmp_path))
    settings = ServerSettings()
    assert settings.screenshot_dir == tmp_path / "screenshots"


def test_db_path_under_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``db_path`` 는 ``data_dir/okdoit.db`` 다 (단계 02 부터 실제 사용)."""
    monkeypatch.setenv("OKDOIT_DATA_DIR", str(tmp_path))
    settings = ServerSettings()
    assert settings.db_path == tmp_path / "okdoit.db"
