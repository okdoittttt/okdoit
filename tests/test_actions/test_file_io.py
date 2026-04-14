"""파일 입출력 액션 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.actions.file_io import upload_file


@pytest.mark.asyncio
async def test_upload_file_calls_set_input_files(tmp_path):
    """존재하는 파일 경로로 set_input_files()를 호출하는지 확인한다."""
    test_file = tmp_path / "test.pdf"
    test_file.write_text("dummy")

    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.set_input_files = AsyncMock()
    mock_page.get_by_label = MagicMock(return_value=mock_locator)

    await upload_file(mock_page, {"type": "upload_file", "value": "파일 선택", "path": str(test_file)})

    mock_locator.first.set_input_files.assert_called_once_with(str(test_file), timeout=10_000)


@pytest.mark.asyncio
async def test_upload_file_raises_when_file_not_exists():
    """존재하지 않는 파일 경로를 지정하면 ValueError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()

    with pytest.raises(ValueError, match="파일이 존재하지 않습니다"):
        await upload_file(mock_page, {"type": "upload_file", "value": "파일 선택", "path": "/not/exist/file.pdf"})


@pytest.mark.asyncio
async def test_upload_file_raises_when_path_is_empty_list():
    """path가 빈 리스트이면 ValueError를 발생시키는지 확인한다."""
    mock_page = AsyncMock()

    with pytest.raises(ValueError, match="path가 비어있습니다"):
        await upload_file(mock_page, {"type": "upload_file", "value": "파일 선택", "path": []})


@pytest.mark.asyncio
async def test_upload_file_raises_when_all_locators_fail(tmp_path):
    """모든 locator가 실패하면 RuntimeError를 발생시키는지 확인한다."""
    test_file = tmp_path / "test.pdf"
    test_file.write_text("dummy")

    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.set_input_files = AsyncMock(side_effect=Exception("not found"))
    mock_page.get_by_label.return_value = mock_locator
    mock_page.get_by_text.return_value = mock_locator
    mock_page.locator.return_value = mock_locator

    with pytest.raises(RuntimeError, match="파일 업로드 요소를 찾을 수 없습니다"):
        await upload_file(mock_page, {"type": "upload_file", "value": "없는버튼", "path": str(test_file)})


@pytest.mark.asyncio
async def test_upload_multiple_files(tmp_path):
    """path가 리스트이면 여러 파일을 set_input_files()에 전달하는지 확인한다."""
    file_a = tmp_path / "a.jpg"
    file_b = tmp_path / "b.jpg"
    file_a.write_text("a")
    file_b.write_text("b")

    mock_page = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first.set_input_files = AsyncMock()
    mock_page.get_by_label = MagicMock(return_value=mock_locator)

    await upload_file(mock_page, {"type": "upload_file", "value": "파일 선택", "path": [str(file_a), str(file_b)]})

    mock_locator.first.set_input_files.assert_called_once_with(
        [str(file_a), str(file_b)], timeout=10_000
    )
