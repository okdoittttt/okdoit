"""세션 상태와 이벤트 큐 + SQLite 영속화.

각 ``/run`` 요청은 하나의 ``Session`` 을 만들고, ``AgentRunner`` 가 그 세션에
이벤트를 쏘는 동안 WebSocket 핸들러는 큐에서 envelope 을 꺼내 클라이언트에 push 한다.

PR3 부터:
    - 모든 publish 는 ``Session._seq`` 카운터로 단조 증가 seq 를 받아 ``WireMessage``
      envelope 으로 감싸진다. 이 envelope 이 큐와 DB 양쪽으로 흐른다.
    - ``SqliteSessionStore`` 가 ``_active`` 인메모리 캐시(asyncio primitive 보유) +
      DB 영속화(``SessionRepository`` / ``EventRepository`` / ``ScreenshotRepository``)
      를 합친 책임을 진다. ``Session`` 객체 자체는 절대 DB 에 가지 않는다.

설계 세부는 ``REFACTOR_PLAN_LOCAL_DB.md`` §4.3 참조.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from server.internal.events import ServerEvent, WireMessage
from server.internal.session_models import SessionSnapshot, SessionStatus
from server.internal.storage import open_connection
from server.internal.storage.repositories import (
    EventRepository,
    ScreenshotRepository,
    SessionRepository,
)

logger = logging.getLogger(__name__)


# ── 상수 ────────────────────────────────────────────────────────

# 단일 세션 큐의 최대 크기. 클라이언트가 매우 느릴 때 메모리 폭발 방지용.
# 초과 시 가장 오래된 envelope 을 폐기하고 새 envelope 을 enqueue 한다.
SESSION_QUEUE_MAXSIZE: int = 1024

# WS 가 None envelope 을 받으면 정상 종료 신호로 해석한다.
_QUEUE_SENTINEL: object = object()


PersistCallback = Callable[[WireMessage], None]
"""sync 콜백. ``Session.publish`` 가 ``asyncio.to_thread`` 로 감싸 호출한다."""


__all__ = [
    "PersistCallback",
    "SESSION_QUEUE_MAXSIZE",
    "Session",
    "SessionSnapshot",
    "SessionStatus",
    "SessionStore",
    "SqliteSessionStore",
]


class Session:
    """단일 작업의 인메모리 상태(asyncio primitives + 큐)를 보관한다.

    영속화는 ``SqliteSessionStore`` 가 콜백 주입(``_persist``)으로 위임하므로
    이 클래스는 DB 의존성이 0이다 — 단위 테스트에서도 그대로 사용 가능.

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

        # transport seq + DB 영속화 콜백. store 가 ``create`` 에서 주입한다.
        self._seq: int = 0
        self._persist: Optional[PersistCallback] = None

    # ── 이벤트 발행 / 수신 ──────────────────────────────────────

    async def publish(self, event: ServerEvent) -> None:
        """이벤트에 seq 를 부여해 envelope 으로 감싸고, 큐 + DB 양쪽에 흘려보낸다.

        큐가 가득 찼다면 가장 오래된 envelope 을 버리고 새 envelope 을 넣는다.
        UI 가 일시적으로 느려도 sidecar 가 막히지 않게 하는 안전장치.

        DB persist 는 ``_persist`` 콜백이 있을 때만 시도하고, 실패해도 runner
        흐름은 막지 않는다(로그만 남김) — 이벤트 누락이 사용자 흐름 차단보다 낫다.

        Args:
            event: ``server.internal.events.ServerEvent`` 합집합 중 하나.
        """
        self._seq += 1
        wire = WireMessage(seq=self._seq, event=event)

        # 1) 인메모리 큐 — WS 핸들러가 가져간다.
        try:
            self._queue.put_nowait(wire)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(wire)

        # 2) DB 영속화 — replay / 재시작 후 GET /sessions 에서 보존된다.
        if self._persist is not None:
            try:
                await asyncio.to_thread(self._persist, wire)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "이벤트 영속화 실패: session_id=%s seq=%d type=%s",
                    self.id,
                    wire.seq,
                    event.type,
                )

    async def next_event(self) -> Optional[WireMessage]:
        """다음 envelope 을 큐에서 꺼낸다. 종료 sentinel 이면 None 반환.

        Returns:
            ``WireMessage`` 또는 종료 신호 시 None.
        """
        item = await self._queue.get()
        if item is _QUEUE_SENTINEL:
            return None
        return item  # type: ignore[no-any-return]

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


class SqliteSessionStore:
    """활성 세션 핸들 캐시 + SQLite 영속화의 두 책임을 합친 store.

    - **활성 캐시(``_active``)**: 현재 RUNNING / PAUSED / 막 만들어진 세션의
      asyncio primitive(큐, pause/stop event)를 보관. 이 객체는 절대 DB 에 가지 않는다.
    - **영속화 위임**: 모든 SQL 호출은 Repository 3종을 거친다. 메서드별로
      짧은 connection 을 새로 열고 닫는다(SQLite open/close 비용은 마이크로초 단위).

    ``Session.publish`` 가 호출하는 ``_persist`` 콜백은 ``create`` 에서 주입하므로
    ``routes/sessions.py`` 의 직접 publish (pause/resume) 도 자동으로 영속화된다.

    Attributes:
        db_path: SQLite 파일 절대 경로. ``ServerSettings.db_path`` 그대로.
    """

    # 라우터/테스트가 한 번에 보여줄 세션 개수. 너무 크면 사이드바가 느려지고,
    # 너무 작으면 사용자가 과거 세션을 못 본다.
    LIST_LIMIT_DEFAULT: int = 100

    def __init__(self, db_path: Path) -> None:
        """저장소를 초기화한다.

        Args:
            db_path: SQLite 파일 절대 경로.
        """
        self._db_path = db_path
        self._active: dict[str, Session] = {}

    def _new_conn(self) -> sqlite3.Connection:
        """짧은 작업용 connection 을 새로 만든다. 호출 측이 닫는다."""
        return open_connection(self._db_path)

    # ── 라이프사이클 ──────────────────────────────────────────

    def create(self, task: str, headless: bool = True) -> Session:
        """새 세션 객체를 만들고 ``sessions`` row 를 insert + persist 콜백 연결.

        Args:
            task: 사용자 입력 태스크.
            headless: 브라우저 헤드리스 여부 (실행 시점 스냅샷).

        Returns:
            인메모리 ``Session`` 객체. asyncio primitive 보유.
        """
        session = Session(task=task)
        # publish 가 호출하는 sync 콜백 — runner 가 어디서 부르든 같은 경로로 영속화.
        session._persist = self._make_persist(session.id)
        self._active[session.id] = session

        conn = self._new_conn()
        try:
            SessionRepository(conn).insert(
                session_id=session.id,
                task=task,
                headless=headless,
                llm_provider=None,
                llm_model=None,
            )
        finally:
            conn.close()
        return session

    def _make_persist(self, session_id: str) -> PersistCallback:
        """세션마다 captured ``session_id`` 가 다른 sync persist 콜백을 만든다.

        Args:
            session_id: 캡처할 세션 식별자.

        Returns:
            ``WireMessage`` 1건을 받아 ``events`` 테이블에 append 하는 sync 함수.
        """
        db_path = self._db_path

        def _persist(wire: WireMessage) -> None:
            conn = open_connection(db_path)
            try:
                EventRepository(conn).append(session_id, wire.event, wire.seq)
            finally:
                conn.close()

        return _persist

    # ── 조회 ─────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[Session]:
        """활성 세션 핸들을 반환한다 (DB 조회 X).

        과거(비활성) 세션은 ``snapshot_of`` 로 따로 가져간다.

        Args:
            session_id: 세션 식별자.

        Returns:
            활성 캐시에 있으면 ``Session``, 없으면 None.
        """
        return self._active.get(session_id)

    def list_active(self) -> list[Session]:
        """현재 활성 캐시의 ``Session`` 객체들을 반환한다.

        앱 종료 시 ``request_stop()`` 일괄 호출 같은 인메모리 작업에서만 쓴다.
        외부 응답에는 ``list_all`` 을 사용해야 한다.

        Returns:
            활성 ``Session`` 리스트 (순서 보장 안 됨).
        """
        return list(self._active.values())

    def list_all(self, limit: int = LIST_LIMIT_DEFAULT) -> list[SessionSnapshot]:
        """DB 의 최근 세션 ``limit`` 개를 created_at 내림차순으로 반환한다.

        활성/비활성 둘 다 포함된다 — 활성 세션은 DB row 도 같이 갱신되기 때문.

        Args:
            limit: 반환할 최대 개수.

        Returns:
            ``SessionSnapshot`` 리스트.
        """
        conn = self._new_conn()
        try:
            return SessionRepository(conn).list_all(limit=limit)
        finally:
            conn.close()

    def snapshot_of(self, session_id: str) -> Optional[SessionSnapshot]:
        """DB 에서 단일 세션 스냅샷을 가져온다 (활성/비활성 모두).

        Args:
            session_id: 세션 식별자.

        Returns:
            row 가 있으면 ``SessionSnapshot``, 없으면 None.
        """
        conn = self._new_conn()
        try:
            return SessionRepository(conn).get(session_id)
        finally:
            conn.close()

    def screenshot_paths_for(self, session_id: str) -> list[str]:
        """세션의 스크린샷 경로 목록을 시간순으로 반환한다 (artifact DB fallback 용).

        Args:
            session_id: 세션 식별자.

        Returns:
            절대 경로 문자열 리스트 (없으면 빈 리스트).
        """
        conn = self._new_conn()
        try:
            return ScreenshotRepository(conn).list_for(session_id)
        finally:
            conn.close()

    def evict(self, session_id: str) -> None:
        """활성 캐시에서 세션을 제거한다 (DB row 는 보존).

        Args:
            session_id: 세션 식별자. 없어도 조용히 무시한다.
        """
        self._active.pop(session_id, None)


# 외부 import 호환을 위한 별칭. 새 코드에서는 ``SqliteSessionStore`` 를 직접 쓴다.
SessionStore = SqliteSessionStore
