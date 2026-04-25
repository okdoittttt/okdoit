"""LangGraph 에이전트를 한 세션 단위로 실행하고 단계별 이벤트를 발행한다.

``agent.py:_run`` 의 책임을 ``AgentRunner`` 클래스로 옮긴 것이다. 차이점:
    - ``print`` 대신 ``Session.publish(...)`` 로 구조화 이벤트를 쏜다.
    - 노드 사이마다 pause/stop 플래그를 확인한다.
    - 종료 / 에러 / 사용자 중단을 모두 별도 이벤트로 알린다.

이벤트 *생성* 자체는 ``server.internal.event_builders`` 의 순수 함수에 위임하고,
이 모듈은 흐름 제어 + ``publish`` 부수효과만 다룬다. 세부 설계는
``.plan/01-backend-fastapi.md`` "AgentRunner 설계" 섹션 참조.
"""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

from core.browser import BrowserManager
from core.graph import create_graph, initial_state
from core.state import AgentState
from server.internal.event_builders import (
    build_plan_created,
    build_plan_replanned,
    build_step_acted,
    build_step_observed,
    build_step_thinking,
    build_step_verified,
    build_subtask_activated,
    find_active_subtask_index,
)
from server.internal.events import (
    SessionErrored,
    SessionFinished,
    SessionStarted,
    SessionStopped,
)
from server.internal.session import Session, SessionStatus

logger = logging.getLogger(__name__)


class AgentRunner:
    """단일 세션의 그래프 실행과 이벤트 발행을 담당한다.

    하나의 세션은 정확히 하나의 ``AgentRunner.run()`` 호출에 대응한다.

    Attributes:
        session: 이벤트 / 제어 플래그를 공유하는 ``Session``.
        manager: ``BrowserManager`` 인스턴스. 외부에서 라이프사이클을 결정한다.
    """

    def __init__(self, session: Session, manager: BrowserManager) -> None:
        """러너를 초기화한다.

        Args:
            session: 이벤트와 pause/stop 플래그를 공유할 세션.
            manager: 이미 생성됐지만 ``start()`` 는 아직 호출되지 않은 매니저.
                runner 가 ``start()`` / ``stop()`` 라이프사이클을 책임진다.
        """
        self.session = session
        self.manager = manager
        self._prev_active_subtask: int = -1

    # ── 진입점 ────────────────────────────────────────────────

    async def run(self) -> None:
        """그래프를 스트리밍 실행하면서 이벤트를 발행한다.

        예외는 잡아서 ``SessionErrored`` 로 변환하고, 어떤 경우에도 브라우저가
        정리되도록 ``finally`` 에서 ``manager.stop()`` 을 호출한다. 마지막에는
        WS 가 깨끗하게 빠지도록 ``session.close_stream()`` 을 호출한다.
        """
        try:
            await self._publish_started()
            await self.manager.start()
            await self._stream_graph(self.session.task)
        except Exception as exc:  # noqa: BLE001
            logger.exception("AgentRunner 실패: %s", exc)
            await self._publish_errored(str(exc))
        finally:
            try:
                await self.manager.stop()
            except Exception:  # noqa: BLE001
                logger.exception("BrowserManager.stop 실패(무시)")
            await self.session.close_stream()

    # ── 흐름 제어 ─────────────────────────────────────────────

    async def _stream_graph(self, task: str) -> None:
        """그래프를 ``astream`` 으로 돌리며 노드 결과를 이벤트로 변환한다.

        Args:
            task: 사용자 입력 태스크 문자열.
        """
        graph = create_graph()
        state = initial_state(task)
        final: AgentState = state

        run_config = RunnableConfig(
            run_name="okdoit_sidecar_run",
            tags=["sidecar"],
            metadata={"task": task, "session_id": self.session.id},
        )

        async for step in graph.astream(state, config=run_config):
            if await self._handle_control_flags():
                return

            for node_name, node_state in step.items():
                final = node_state
                await self._dispatch_node_event(node_name, node_state)

        await self._publish_finished(final)

    async def _handle_control_flags(self) -> bool:
        """pause/stop 플래그를 처리한다.

        Returns:
            stop 이 요청되어 루프를 빠져나가야 하면 True. 정상 진행이면 False.
        """
        if self.session.stop_requested:
            await self._publish_stopped()
            return True

        await self.session.wait_if_paused()

        if self.session.stop_requested:
            await self._publish_stopped()
            return True
        return False

    # ── 노드 → 이벤트 디스패치 ────────────────────────────────

    async def _dispatch_node_event(self, node_name: str, state: AgentState) -> None:
        """노드 이름에 따라 0~2개의 이벤트를 발행한다.

        Args:
            node_name: 직전에 실행된 노드 이름.
            state: 해당 노드가 반환한 ``AgentState``.
        """
        # 어떤 노드든 iterations 가 들어있으면 스냅샷을 갱신한다.
        self.session.latest_iterations = int(state.get("iterations", 0))
        sid = self.session.id

        if node_name == "plan":
            await self.session.publish(build_plan_created(sid, state))
        elif node_name == "replan":
            await self.session.publish(build_plan_replanned(sid, state))
            # replan 후엔 active subtask 추적을 리셋해 다음 verify 에서 재발행되게 한다.
            self._prev_active_subtask = -1
        elif node_name == "observe":
            await self.session.publish(build_step_observed(sid, state))
            # observe 마다 새 스크린샷이 만들어진다. 아티팩트 응답에서 갤러리로 노출.
            screenshot = state.get("screenshot_path")
            if screenshot:
                self.session.screenshot_paths.append(screenshot)
        elif node_name == "think":
            event = build_step_thinking(sid, state)
            if event is not None:
                await self.session.publish(event)
        elif node_name == "act":
            await self.session.publish(build_step_acted(sid, state))
        elif node_name == "verify":
            await self.session.publish(build_step_verified(sid, state))
            await self._maybe_emit_subtask_activated(state)
        # 그 외 노드는 무시(현재는 없음).

    async def _maybe_emit_subtask_activated(self, state: AgentState) -> None:
        """active subtask 가 바뀌었을 때만 ``SubtaskActivated`` 를 발행한다.

        ``_prev_active_subtask`` 인스턴스 상태를 이용해 같은 인덱스에서는
        중복 발행을 막는다.

        Args:
            state: verify 노드가 갱신한 직후의 상태.
        """
        subtasks = state.get("subtasks") or []
        active_idx = find_active_subtask_index(subtasks)
        if active_idx == -1 or active_idx == self._prev_active_subtask:
            return

        self._prev_active_subtask = active_idx
        await self.session.publish(
            build_subtask_activated(self.session.id, subtasks, active_idx)
        )

    # ── 세션 라이프사이클 이벤트 ──────────────────────────────

    async def _publish_started(self) -> None:
        """``session.started`` 이벤트를 발행하고 상태를 RUNNING 으로 전환한다."""
        self.session.status = SessionStatus.RUNNING
        await self.session.publish(
            SessionStarted(session_id=self.session.id, task=self.session.task)
        )

    async def _publish_finished(self, state: AgentState) -> None:
        """그래프가 정상 종료된 후 결과 이벤트를 발행한다.

        ``state["error"]`` 가 있으면 errored 로, 그렇지 않으면 finished 로 분기.

        Args:
            state: ``astream`` 마지막 스텝에서 받은 최종 ``AgentState``.
        """
        result_text = state.get("extracted_result") or state.get("result")
        error = state.get("error")
        iterations = int(state.get("iterations", 0))

        self.session.latest_iterations = iterations
        self.session.latest_result = result_text
        self.session.latest_error = error
        # 종료 시점의 subtasks / collected_data 를 보존한다(아티팩트 응답용).
        self.session.latest_subtasks = list(state.get("subtasks") or [])
        self.session.latest_collected_data = dict(state.get("collected_data") or {})

        if error:
            self.session.status = SessionStatus.ERRORED
            await self.session.publish(
                SessionErrored(session_id=self.session.id, error=error)
            )
            return

        self.session.status = SessionStatus.FINISHED
        await self.session.publish(
            SessionFinished(
                session_id=self.session.id,
                result=result_text,
                iterations=iterations,
            )
        )

    async def _publish_errored(self, message: str) -> None:
        """예외 캐치 분기에서 호출되는 errored 이벤트 발행 헬퍼.

        Args:
            message: 사용자(UI)에 노출할 에러 메시지.
        """
        self.session.status = SessionStatus.ERRORED
        self.session.latest_error = message
        await self.session.publish(
            SessionErrored(session_id=self.session.id, error=message)
        )

    async def _publish_stopped(self) -> None:
        """사용자 stop 요청에 의한 종료 이벤트를 발행한다."""
        self.session.status = SessionStatus.STOPPED
        await self.session.publish(SessionStopped(session_id=self.session.id))
