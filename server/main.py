"""sidecar CLI 진입점.

uvicorn 으로 ``server.internal.app:app`` 을 띄운다. 실제 라우터/라이프사이클은 ``app.py``
에 있고, 이 파일은 환경변수에서 host/port/log_level 만 읽어 uvicorn 에 넘긴다.

Examples:
    python -m server.main
    OKDOIT_PORT=9000 python -m server.main
"""

from __future__ import annotations

from dotenv import load_dotenv

import uvicorn

from server.internal.config import get_settings


def main() -> None:
    """uvicorn 으로 sidecar 를 띄운다."""
    load_dotenv()
    # ``get_settings`` 는 lru_cache 로 캐싱되므로 여기서 한 번 읽어둔다.
    settings = get_settings()
    uvicorn.run(
        "server.internal.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    main()
