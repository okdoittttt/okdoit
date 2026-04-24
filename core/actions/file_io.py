"""파일 입출력 액션 - 파일 업로드."""

import os
from typing import Union

from playwright.async_api import Page

from core.actions._registry import registry
from core.actions.result import ActionErrorCode, ActionResult

_UPLOAD_TIMEOUT = 10_000


@registry.register("upload_file")
async def upload_file(page: Page, action: dict) -> ActionResult:
    """파일 업로드 입력 요소에 파일을 설정한다.

    value로 파일 입력 요소를 찾고, path에 지정된 파일을 set_input_files()로 업로드한다.
    get_by_label → get_by_text → input[type='file'] → locator 순서로 시도한다.

    Args:
        page: 현재 Playwright 페이지
        action: {"type": "upload_file", "value": "<target>", "path": "<filepath>"}
                또는 {"type": "upload_file", "value": "<target>", "path": ["<path1>", "<path2>"]}

    Returns:
        ActionResult. path 검증 실패는 INVALID_ARGUMENT로 명시적 fail로 반환한다.

    Raises:
        RuntimeError: 파일 업로드 입력 요소를 찾을 수 없는 경우.
    """
    target: str = action["value"]
    raw_path: Union[str, list[str]] = action["path"]

    paths: list[str] = [raw_path] if isinstance(raw_path, str) else list(raw_path)
    if not paths:
        return ActionResult.fail(
            ActionErrorCode.INVALID_ARGUMENT,
            "upload_file: path가 비어있습니다",
        )

    for p in paths:
        if not os.path.exists(p):
            return ActionResult.fail(
                ActionErrorCode.INVALID_ARGUMENT,
                f"upload_file: 파일이 존재하지 않습니다: '{p}'",
            )

    upload_paths: Union[str, list[str]] = paths[0] if len(paths) == 1 else paths

    for locator in [
        page.get_by_label(target),
        page.get_by_text(target, exact=False),
        page.locator("input[type='file']"),
        page.locator(target),
    ]:
        try:
            await locator.first.set_input_files(upload_paths, timeout=_UPLOAD_TIMEOUT)
            return ActionResult.ok()
        except Exception:
            continue

    raise RuntimeError(f"파일 업로드 요소를 찾을 수 없습니다: '{target}'")
