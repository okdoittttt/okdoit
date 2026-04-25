"""``server.internal.runner.AgentRunner`` 가 노드 결과를 올바른 이벤트로 변환하는지 검증.

``core.graph.create_graph`` 와 ``core.browser.BrowserManager`` 를 모킹해서
실제 LLM/Playwright 호출 없이 이벤트 시퀀스를 검증한다. 빌더 함수의 단위 테스트는
``test_event_builders.py`` 참조.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.internal.events import (
    PlanCreated,
    PlanReplanned,
    SessionFinished,
    SessionStarted,
    SessionStopped,
    StepActed,
    StepObserved,
    StepThinking,
    StepVerified,
    SubtaskActivated,
)
from server.internal.runner import AgentRunner
from server.internal.session import Session, SessionStatus


# ── 헬퍼 ────────────────────────────────────────────────────────


def _make_state(**overrides: Any) -> dict[str, Any]:
    """그래프 노드가 반환하는 state 모방용 최소 dict.

    ``AgentRunner`` 는 ``state.get(...)`` 로만 읽으므로 누락 필드는 자동으로
    None / 0 으로 처리된다.
    """
    base: dict[str, Any] = {
        "iterations": 0,
        "is_done": False,
        "consecutive_errors": 0,
        "current_url": "",
        "screenshot_path": None,
        "selector_map": {},
        "history_items": [],
        "last_action": None,
        "last_action_result": None,
        "subtasks": [],
        "replan_count": 0,
        "plan_stale": False,
        "result": None,
        "extracted_result": None,
        "error": None,
    }
    base.update(overrides)
    return base


def _fake_graph(steps: list[dict[str, dict[str, Any]]]) -> Any:
    """``astream`` 이 주어진 시퀀스를 그대로 yield 하는 가짜 그래프.

    Args:
        steps: ``[{node_name: state_dict}, ...]`` 형태.
    """
    fake = MagicMock()

    async def _astream(state: Any, config: Any = None):  # type: ignore[no-untyped-def]
        for s in steps:
            yield s

    fake.astream = _astream
    return fake


def _fake_manager() -> MagicMock:
    """start/stop 만 갖는 BrowserManager 모킹."""
    m = MagicMock()
    m.start = AsyncMock()
    m.stop = AsyncMock()
    return m


async def _drain_events(session: Session) -> list[Any]:
    """세션 큐에서 종료 sentinel 까지 모두 꺼낸다."""
    collected: list[Any] = []
    while True:
        evt = await session.next_event()
        if evt is None:
            break
        collected.append(evt)
    return collected


# ── 통합: 이벤트 시퀀스 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_emits_full_event_sequence_for_simple_run() -> None:
    """plan→observe→think→act→verify(is_done) 한 사이클의 이벤트를 검증한다."""
    plan_state = _make_state(
        subtasks=[{"description": "검색", "done": False}, {"description": "확인", "done": False}],
    )
    observe_state = _make_state(
        iterations=1,
        current_url="https://example.com",
        screenshot_path="/tmp/s.png",
        selector_map={0: {}, 1: {}, 2: {}},
        subtasks=plan_state["subtasks"],
    )
    think_state = _make_state(
        iterations=1,
        history_items=[
            {"step": 1, "thought": "검색창 입력", "action": {"name": "type"}, "memory_update": None}
        ],
        subtasks=plan_state["subtasks"],
    )
    act_state = _make_state(
        iterations=2,
        last_action="type(value=hi)",
        last_action_result={
            "success": True,
            "error_code": None,
            "error_message": None,
            "extracted": None,
            "recovery_hint": None,
        },
        subtasks=plan_state["subtasks"],
    )
    verify_state = _make_state(
        iterations=2,
        is_done=True,
        result="완료",
        subtasks=[{"description": "검색", "done": True}, {"description": "확인", "done": True}],
    )

    steps = [
        {"plan": plan_state},
        {"observe": observe_state},
        {"think": think_state},
        {"act": act_state},
        {"verify": verify_state},
    ]

    session = Session(task="검색해줘")
    runner = AgentRunner(session=session, manager=_fake_manager())

    with patch("server.internal.runner.create_graph", return_value=_fake_graph(steps)):
        await runner.run()

    events = await _drain_events(session)
    types = [type(e) for e in events]

    assert types[0] is SessionStarted
    assert types[-1] is SessionFinished
    assert PlanCreated in types
    assert StepObserved in types
    assert StepThinking in types
    assert StepActed in types
    assert StepVerified in types

    finished = [e for e in events if isinstance(e, SessionFinished)][0]
    assert finished.result == "완료"
    assert finished.iterations == 2
    assert session.status == SessionStatus.FINISHED


@pytest.mark.asyncio
async def test_runner_emits_subtask_activated_only_on_change() -> None:
    """active subtask 가 바뀐 verify 직후에만 ``subtask.activated`` 가 발행된다."""
    subtasks_v1 = [
        {"description": "a", "done": True},
        {"description": "b", "done": False},
    ]
    subtasks_v2 = [
        {"description": "a", "done": True},
        {"description": "b", "done": True},
    ]

    steps = [
        {"plan": _make_state(subtasks=[{"description": "a", "done": False}, {"description": "b", "done": False}])},
        {"verify": _make_state(iterations=1, subtasks=subtasks_v1)},
        {"verify": _make_state(iterations=2, subtasks=subtasks_v1)},  # 동일 active → 추가 발행 X
        {"verify": _make_state(iterations=3, is_done=True, result="ok", subtasks=subtasks_v2)},
    ]

    session = Session(task="t")
    runner = AgentRunner(session=session, manager=_fake_manager())
    with patch("server.internal.runner.create_graph", return_value=_fake_graph(steps)):
        await runner.run()

    events = await _drain_events(session)
    activated = [e for e in events if isinstance(e, SubtaskActivated)]
    assert len(activated) == 1
    assert activated[0].index == 1
    assert activated[0].description == "b"


@pytest.mark.asyncio
async def test_runner_emits_plan_replanned_event() -> None:
    """replan 노드 결과는 ``plan.replanned`` 로 변환된다."""
    new_subtasks = [{"description": "다시", "done": False}]
    steps = [
        {"plan": _make_state(subtasks=[{"description": "old", "done": False}])},
        {"replan": _make_state(plan_stale=True, replan_count=1, subtasks=new_subtasks)},
        {"verify": _make_state(iterations=1, is_done=True, result="ok", subtasks=[{"description": "다시", "done": True}])},
    ]
    session = Session(task="t")
    runner = AgentRunner(session=session, manager=_fake_manager())
    with patch("server.internal.runner.create_graph", return_value=_fake_graph(steps)):
        await runner.run()

    events = await _drain_events(session)
    replanned = [e for e in events if isinstance(e, PlanReplanned)]
    assert len(replanned) == 1
    assert replanned[0].replan_count == 1
    assert replanned[0].subtasks[0]["description"] == "다시"
    assert "정체" in replanned[0].reason  # plan_stale 경로


@pytest.mark.asyncio
async def test_runner_stops_when_request_stop_set_before_first_step() -> None:
    """루프 진입 직전에 stop 이 들어와 있으면 첫 스텝 후 즉시 빠진다."""
    steps = [
        {"plan": _make_state(subtasks=[])},
        {"observe": _make_state(iterations=1)},
        {"think": _make_state(iterations=1)},
    ]

    session = Session(task="t")
    session.request_stop()

    runner = AgentRunner(session=session, manager=_fake_manager())
    with patch("server.internal.runner.create_graph", return_value=_fake_graph(steps)):
        await runner.run()

    events = await _drain_events(session)
    assert any(isinstance(e, SessionStopped) for e in events)
    assert session.status == SessionStatus.STOPPED


@pytest.mark.asyncio
async def test_runner_publishes_error_event_when_browser_start_fails() -> None:
    """브라우저 시작 실패 시 ``session.errored`` 가 발행되고 status 가 ERRORED."""
    session = Session(task="t")
    bad_manager = _fake_manager()
    bad_manager.start = AsyncMock(side_effect=RuntimeError("playwright down"))

    runner = AgentRunner(session=session, manager=bad_manager)
    await runner.run()

    events = await _drain_events(session)
    errored = [e for e in events if e.type == "session.errored"]
    assert len(errored) == 1
    assert "playwright down" in errored[0].error
    assert session.status == SessionStatus.ERRORED


@pytest.mark.asyncio
async def test_runner_accumulates_screenshot_paths_on_observe() -> None:
    """observe 노드 결과의 screenshot_path 가 ``session.screenshot_paths`` 에 누적된다."""
    steps = [
        {"plan": _make_state(subtasks=[{"description": "a", "done": False}])},
        {"observe": _make_state(iterations=1, screenshot_path="/tmp/step1.png")},
        {"observe": _make_state(iterations=2, screenshot_path="/tmp/step2.png")},
        {"observe": _make_state(iterations=3, screenshot_path=None)},  # None 은 무시
        {"verify": _make_state(iterations=3, is_done=True, result="ok", subtasks=[{"description": "a", "done": True}])},
    ]
    session = Session(task="t")
    runner = AgentRunner(session=session, manager=_fake_manager())
    with patch("server.internal.runner.create_graph", return_value=_fake_graph(steps)):
        await runner.run()

    assert session.screenshot_paths == ["/tmp/step1.png", "/tmp/step2.png"]


@pytest.mark.asyncio
async def test_runner_preserves_subtasks_and_collected_data_on_finish() -> None:
    """정상 종료 시 ``latest_subtasks`` / ``latest_collected_data`` 가 보존된다."""
    final_subtasks = [{"description": "a", "done": True}]
    collected = {"서울": {"information": "맑음", "collected": True}}
    steps = [
        {"plan": _make_state(subtasks=final_subtasks)},
        {
            "verify": _make_state(
                iterations=1,
                is_done=True,
                result="끝",
                subtasks=final_subtasks,
                collected_data=collected,
            )
        },
    ]
    session = Session(task="t")
    runner = AgentRunner(session=session, manager=_fake_manager())
    with patch("server.internal.runner.create_graph", return_value=_fake_graph(steps)):
        await runner.run()

    assert session.latest_subtasks == final_subtasks
    assert session.latest_collected_data == collected
    assert session.latest_result == "끝"
