"""세션 상태와 이벤트 큐 관리.

각 ``/run`` 요청은 하나의 ``Session`` 을 만들고, ``AgentRunner`` 가 그 세션에
이벤트를 쏘는 동안 WebSocket 핸들러는 큐에서 이벤트를 꺼내 클라이언트에 push 한다.

이 모듈은 순수 도메인 정의만 담는다. 프로세스 단위 ``SessionStore`` 싱글톤은
``server.internal.deps`` 가 소유하고 FastAPI 의존성 주입으로 노출한다. 설계 세부는
``.plan/01-backend-fastapi.md`` 의 "SessionStore 설계" 참조.
"""

from __future__ import annotations

import asyncio
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from server.internal.events import ServerEvent


# ── 상수 ────────────────────────────────────────────────────────

# 단일 세션 큐의 최대 크기. 클라이언트가 매우 느릴 때 메모리 폭발 방지용.
# 초과 시 가장 오래된 이벤트를 폐기하고 새 이벤트를 enqueue 한다.
SESSION_QUEUE_MAXSIZE: int = 1024

# WS 가 None 이벤트를 받으면 정상 종료 신호로 해석한다.
# (asyncio.Queue.get() 이 차단되지 않게 하기 위한 sentinel)
_QUEUE_SENTINEL: object = object()


class SessionStatus(str, Enum):
    """세션 라이프사이클 상태."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ERRORED = "errored"
    STOPPED = "stopped"


class SessionSnapshot(BaseModel):
    """``GET /sessions/{id}`` 응답용 직렬화 스냅샷.

    런타임 객체(``Session``) 자체에는 asyncio primitive 가 들어있어
    그대로 직렬화할 수 없다. 외부 노출용 별도 모델이다.

    Attributes:
        id: 세션 식별자(uuid4).
        task: 사용자가 입력한 작업 문자열.
        status: 현재 라이프사이클 상태(``SessionStatus``).
        iterations: 가장 최근에 본 ``AgentState["iterations"]`` 값.
        result: 정상 종료 시 결과 텍스트. 미종료 / 실패 시 None.
        error: 에러 종료 시 메시지. 정상 / 미종료 시 None.
    """

    id: str
    task: str
    status: SessionStatus
    iterations: int = 0
    result: Optional[str] = None
    error: Optional[str] = None


class Session:
    """단일 작업의 상태와 이벤트 큐를 보관한다.

    Attributes:
        id: 세션 식별자(uuid4).
        task: 작업 문자열.
        status: 현재 라이프사이클 상태.
        pause_event: ``set`` 이면 RUNNING(통과), ``clear`` 이면 PAUSED(대기).
        stop_event: ``set`` 이면 다음 노드 진입 직전 루프 탈출 요청.
        latest_iterations: 가장 최근 ``AgentState["iterations"]`` 값(스냅샷용).
        latest_result: 종료 시 결과 텍스트.
        latest_error: 에러 발생 시 메시지.
        latest_subtasks: 종료 시점의 ``AgentState["subtasks"]`` 사본. 아티팩트 응답용.
        latest_collected_data: 종료 시점의 ``AgentState["collected_data"]`` 사본.
        screenshot_paths: observe 노드 실행 때마다 누적된 스크린샷 절대 경로 목록.
    """

    def __init__(self, task: str, session_id: Optional[str] = None) -> None:
        """세션을 초기화한다.

        Args:
            task: 사용자 입력 태스크 문자열.
            session_id: 외부에서 식별자를 지정해야 할 때만 사용. 보통 자동 생성.
        """
        self.id: str = session_id or str(uuid.uuid4())
        self.task: str = task
        self.status: SessionStatus = SessionStatus.IDLE

        self._queue: asyncio.Queue = asyncio.Queue(maxsize=SESSION_QUEUE_MAXSIZE)
        self.pause_event: asyncio.Event = asyncio.Event()
        self.pause_event.set()  # 초기는 RUNNING(통과) 상태
        self.stop_event: asyncio.Event = asyncio.Event()

        self.latest_iterations: int = 0
        self.latest_result: Optional[str] = None
        self.latest_error: Optional[str] = None
        self.latest_subtasks: list[dict[str, Any]] = []
        self.latest_collected_data: dict[str, dict[str, Any]] = {}
        self.screenshot_paths: list[str] = []

    # ── 이벤트 발행 / 수신 ──────────────────────────────────────

    async def publish(self, event: ServerEvent) -> None:
        """이벤트를 큐에 넣고 WS 가 가져갈 수 있게 한다.

        큐가 가득 찼다면 가장 오래된 이벤트를 버리고 새 이벤트를 넣는다.
        UI 가 일시적으로 느려져도 sidecar 가 막히지 않게 하는 안전장치.

        Args:
            event: ``server.internal.events.ServerEvent`` 합집합 중 하나.
        """
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(event)

    async def next_event(self) -> Optional[ServerEvent]:
        """다음 이벤트를 큐에서 꺼낸다. 종료 sentinel 이면 None 반환.

        Returns:
            ``ServerEvent`` 또는 종료 신호 시 None.
        """
        item = await self._queue.get()
        if item is _QUEUE_SENTINEL:
            return None
        return item

    async def close_stream(self) -> None:
        """WS 핸들러가 깨끗하게 빠져나갈 수 있도록 종료 sentinel 을 큐에 넣는다."""
        await self._queue.put(_QUEUE_SENTINEL)

    # ── 제어 플래그 ────────────────────────────────────────────

    def pause(self) -> None:
        """다음 노드 진입 직전에 멈추도록 요청한다."""
        self.pause_event.clear()
        if self.status == SessionStatus.RUNNING:
            self.status = SessionStatus.PAUSED

    def resume(self) -> None:
        """일시정지를 해제한다."""
        self.pause_event.set()
        if self.status == SessionStatus.PAUSED:
            self.status = SessionStatus.RUNNING

    def request_stop(self) -> None:
        """루프 중단을 요청한다. 실제 종료는 runner 가 노드 사이에서 감지한다."""
        self.stop_event.set()
        # PAUSED 상태에서 stop 이 들어오면 pause 도 풀어줘야 runner 가 깨어난다.
        self.pause_event.set()

    async def wait_if_paused(self) -> None:
        """PAUSED 상태라면 resume 까지 대기한다.

        ``runner`` 가 매 노드 결과를 발행한 직후 호출한다. PAUSED 가 아닐 때는
        즉시 반환한다.
        """
        await self.pause_event.wait()

    @property
    def stop_requested(self) -> bool:
        """``stop_event`` 가 세팅됐는지 단축 조회한다."""
        return self.stop_event.is_set()

    # ── 스냅샷 ────────────────────────────────────────────────

    def snapshot(self) -> SessionSnapshot:
        """외부 응답용 스냅샷을 만든다.

        Returns:
            현재 세션 상태의 직렬화 가능한 표현.
        """
        return SessionSnapshot(
            id=self.id,
            task=self.task,
            status=self.status,
            iterations=self.latest_iterations,
            result=self.latest_result,
            error=self.latest_error,
        )


class SessionStore:
    """현재 살아있는 세션들을 보관한다.

    v0.1 은 단일 세션만 사용하지만 dict 기반으로 두면 v0.3 멀티 세션 확장이 자연스럽다.
    """

    def __init__(self) -> None:
        """빈 저장소를 만든다."""
        self._sessions: dict[str, Session] = {}

    def create(self, task: str) -> Session:
        """새 세션을 만들어 등록하고 반환한다.

        Args:
            task: 사용자 입력 태스크 문자열.

        Returns:
            새로 생성된 ``Session``.
        """
        session = Session(task=task)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """식별자로 세션을 조회한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            존재하면 ``Session``, 없으면 ``None``.
        """
        return self._sessions.get(session_id)

    def list_all(self) -> list[Session]:
        """모든 세션을 반환한다(생성 순서 보장 안 됨)."""
        return list(self._sessions.values())

    def remove(self, session_id: str) -> None:
        """세션을 저장소에서 제거한다(메모리 회수용).

        Args:
            session_id: 세션 식별자. 존재하지 않으면 조용히 무시된다.
        """
        self._sessions.pop(session_id, None)
