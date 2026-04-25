"""sidecar CLI 진입점.

uvicorn 으로 ``server.internal.app:app`` 을 띄운다. 실제 라우터/라이프사이클은
``app.py`` 에 있고, 이 파일은 환경변수에서 host/port/log_level 만 읽어 uvicorn 에 넘긴다.

import string(``"server.internal.app:app"``) 대신 app 객체를 직접 전달한다 —
PyInstaller frozen 환경에서 import string 은 정적 분석을 우회해 모듈이 번들에서
누락되는 문제가 있다(v0.4 dmg 빌드에서 실제로 부딪힘). 직접 import 하면 PyInstaller
가 의존성을 추적할 수 있다.

Examples:
    python -m server.main
    OKDOIT_PORT=9000 python -m server.main
"""

from __future__ import annotations

from dotenv import load_dotenv

import uvicorn

from server.internal.app import app
from server.internal.config import get_settings


def main() -> None:
    """uvicorn 으로 sidecar 를 띄운다."""
    load_dotenv()
    # ``get_settings`` 는 lru_cache 로 캐싱되므로 여기서 한 번 읽어둔다.
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
