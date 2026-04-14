"""Plan 노드 - 작업을 단계별 subtask로 분해한다."""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import build_llm
from core.state import AgentState

_PLANNER_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompt" / "planner.md"


async def plan(state: AgentState) -> AgentState:
    """사용자 목표를 받아서 웹 자동화 단계 목록(subtasks)으로 분해한다.

    The Loop의 최초 1회 실행 노드. LLM을 호출해 작업을 3~7개 단계로 나누고
    state의 subtasks 필드에 저장한다. 파싱 실패 시 빈 목록으로 graceful 처리한다.

    Args:
        state: 현재 에이전트 상태 (task 필드 사용)

    Returns:
        subtasks가 업데이트된 AgentState.
    """
    try:
        llm = build_llm()
        system_prompt = _PLANNER_PROMPT_PATH.read_text(encoding="utf-8")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"목표: {state['task']}"),
        ]
        response = await llm.ainvoke(messages)
        response_text = response.content if isinstance(response.content, str) else str(response.content)

        subtasks = _parse_subtasks(response_text)
        return {**state, "subtasks": subtasks}

    except KeyError as e:
        return {**state, "subtasks": [], "error": f"[plan] 환경 변수 누락: {e}"}
    except Exception as e:
        return {**state, "subtasks": [], "error": f"[plan] Unexpected error: {e}"}


def _parse_subtasks(response: str) -> list[dict]:
    """LLM 응답에서 단계 목록을 파싱해 subtask 딕셔너리 리스트로 반환한다.

    Args:
        response: LLM이 반환한 순수 JSON 배열 문자열

    Returns:
        [{"description": str, "done": False}, ...] 형태의 리스트.
        파싱 실패 또는 유효하지 않은 형식이면 빈 리스트를 반환한다.
    """
    try:
        parsed = json.loads(response.strip())
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return [
        {"description": str(step), "done": False}
        for step in parsed
        if step
    ]
