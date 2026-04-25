"""HTTP 요청/응답 스키마 모음.

도메인 이벤트(``server.internal.events``)와 분리해 둔다. REST 스키마는 라우터 한정
계약이고, 이벤트는 WS 프로토콜의 일부라 라이프사이클이 다르다.
"""

from server.internal.schemas.requests import (
    HealthResponse,
    OkResponse,
    RunRequest,
    RunResponse,
)

__all__ = [
    "HealthResponse",
    "OkResponse",
    "RunRequest",
    "RunResponse",
]
