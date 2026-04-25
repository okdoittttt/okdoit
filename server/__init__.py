"""FastAPI sidecar 패키지.

데스크탑 앱이 HTTP/WebSocket으로 ``core/`` 에이전트를 제어하는 진입점이다.

레이아웃:
    server/main.py        — uvicorn CLI 진입점 ("python -m server.main")
    server/internal/      — FastAPI 앱 / 라우터 / 도메인 / 이벤트 / 설정 등 실제 구현

세부 구조는 ``.plan/01-backend-fastapi.md`` 참조.
"""
