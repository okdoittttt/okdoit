"""REST 라우터의 요청 / 응답 Pydantic 모델."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from server.internal.config import get_settings


class RunRequest(BaseModel):
    """``POST /run`` 요청 본문.

    Attributes:
        task: 사용자 입력 태스크 문자열.
        headless: 브라우저 헤드리스 모드 여부. 미지정 시 설정값을 따른다.
    """

    task: str = Field(..., min_length=1)
    headless: Optional[bool] = None


class RunResponse(BaseModel):
    """``POST /run`` 응답.

    Attributes:
        session_id: 새로 만들어진 세션 식별자(uuid4).
    """

    session_id: str


class HealthResponse(BaseModel):
    """``GET /health`` 응답.

    Attributes:
        status: 항상 ``"ok"``. 비정상 상태는 별도 HTTP 코드로 표현한다.
        protocol_version: 클라이언트와 호환성 협상에 사용하는 문자열.
            ``ServerSettings.protocol_version`` 에서 가져온다.
    """

    status: str = "ok"
    protocol_version: str = Field(default_factory=lambda: get_settings().protocol_version)


class OkResponse(BaseModel):
    """단순 성공 응답.

    Attributes:
        ok: 항상 ``True``. 실패는 HTTP 4xx/5xx 코드로 전달된다.
    """

    ok: bool = True
