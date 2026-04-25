"""sidecar 의 실제 구현 모듈 모음.

``server.main`` 은 uvicorn CLI 진입점만 담당하고, FastAPI 앱 / 라우터 / 도메인 /
이벤트 / 설정 등 실제 코드는 모두 이 패키지 안에 있다. 외부에서 호출할 일은 거의
없고, 보통 ``server.main`` 이 ``server.internal.app:app`` 을 uvicorn 에 넘긴다.

세부 구조는 ``.plan/01-backend-fastapi.md`` 참조.
"""
