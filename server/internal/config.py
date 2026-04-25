"""sidecar 런타임 설정.

``pydantic-settings`` 기반 ``ServerSettings`` 한 곳에서 환경변수를 모아 읽는다.
모든 ``OKDOIT_*`` 환경변수는 여기서 정의되고, 라우터/러너는 ``Depends(get_settings)``
또는 직접 ``get_settings()`` 호출로 가져간다.

신규 설정 키를 추가할 때는 이 파일만 수정하면 된다.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """sidecar 의 모든 런타임 옵션.

    Attributes:
        host: 바인딩 호스트. 외부 노출 금지를 위해 기본 ``127.0.0.1``.
        port: 바인딩 포트. main process 가 동적 포트로 덮어쓸 수 있다(v0.2 예정).
        log_level: uvicorn / 애플리케이션 로그 레벨.
        headless_default: ``POST /run`` 의 ``headless`` 미지정 시 사용할 기본값.
        protocol_version: 클라이언트와 호환성 협상용 문자열. 메이저 변경 시 올린다.
    """

    model_config = SettingsConfigDict(
        env_prefix="OKDOIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    headless_default: bool = False
    protocol_version: str = "0.1"


@lru_cache(maxsize=1)
def get_settings() -> ServerSettings:
    """프로세스 단위 단일 ``ServerSettings`` 인스턴스를 반환한다.

    ``lru_cache`` 로 캐싱되므로 어디서 불러도 같은 객체가 나온다. 테스트에서
    설정을 바꾸려면 ``get_settings.cache_clear()`` 후 환경변수를 조정하면 된다.

    Returns:
        ``ServerSettings`` 싱글톤.
    """
    return ServerSettings()
