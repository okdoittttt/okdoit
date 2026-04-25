"""세션 종료 후 결과물(아티팩트) 응답 모델.

``GET /sessions/{id}/artifact`` 가 돌려주는 페이로드. 가벼운 ``SessionSnapshot``
과 달리 사용자에게 보여줄 풍부한 콘텐츠(subtasks 진행도 / 추출 데이터 / 스크린샷
URL) 를 모은다.

스크린샷은 sidecar 의 로컬 파일이지만, 응답에서는 정적 라우트 URL 형태(``/static/screenshots/<filename>``)
로 변환해 클라이언트가 ``<img src>`` 로 바로 표시할 수 있게 한다.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from server.internal.session import SessionStatus


class SessionArtifact(BaseModel):
    """세션 종료 후 결과물 한 묶음.

    Attributes:
        id: 세션 식별자.
        task: 사용자가 입력한 작업 문자열.
        status: 종료 시점의 라이프사이클 상태.
        iterations: 종료 시점의 반복 횟수.
        result: 정상 종료 시 결과 텍스트.
        error: 에러 종료 시 메시지.
        subtasks: 종료 시점의 subtasks 진행도 (``[{"description", "done", ...}]``).
        screenshots: 정적 라우트 URL 목록(``/static/screenshots/<filename>``).
        collected_data: 추출 데이터 사전. 키는 사용자가 정한 식별자.
    """

    id: str
    task: str
    status: SessionStatus
    iterations: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    subtasks: list[dict[str, Any]] = []
    screenshots: list[str] = []
    collected_data: dict[str, dict[str, Any]] = {}
