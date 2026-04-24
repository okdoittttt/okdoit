"""Replan 노드 - 진행 도중 subtasks를 갱신한다.

verify 또는 think가 ``plan_stale=True`` 신호를 보내거나 모든 subtask가 done인데
목표가 미달성일 때 graph 라우터가 이 노드로 분기시킨다.

원래 plan이 처음 한 번만 호출되는 것과 달리, replan은 현재 페이지 상태와 누적
메모리, 최근 액션 히스토리를 입력으로 받아 **남은 작업**을 다시 분해한다.
원 task는 유지한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.context import format_runtime_context_block
from core.llm import build_llm
from core.nodes.plan import _parse_subtasks  # 동일 파서 재사용
from core.state import AgentState, HistoryItem

_REPLANNER_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompt" / "replanner.md"

# replan 입력에 포함할 최근 history_items 개수
_RECENT_HISTORY_FOR_REPLAN: int = 5
# DOM 텍스트는 길어질 수 있으므로 replan 입력에서 잘라서 토큰 절약
_DOM_SNIPPET_CHARS: int = 1500


async def replan(state: AgentState) -> AgentState:
    """현재 진행 상황을 바탕으로 subtasks를 재생성한다.

    The Loop의 후속 분기 노드. ``prompt/replanner.md`` 시스템 프롬프트와 함께
    원 task, 기존 subtasks와 진행도, 누적 memory, 최근 액션, 현재 URL과
    DOM 텍스트(앞부분)를 LLM에 전달한다.

    파싱 실패 또는 LLM 오류 시 plan_stale을 False로 리셋하고 기존 subtasks를
    유지한다(루프가 종료되지 않게). graph 라우터의 MAX_REPLANS 상한이 무한
    재시도를 막는다.

    Args:
        state: 현재 에이전트 상태.

    Returns:
        subtasks가 갱신되고 plan_stale=False, replan_count+1 된 AgentState.
        오류 발생 시 error 필드에만 메시지를 기록하고 다른 필드는 유지한다.
    """
    try:
        llm = build_llm()
        system_prompt = _REPLANNER_PROMPT_PATH.read_text(encoding="utf-8")
        user_msg = _compose_replan_input(state)

        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_msg),
            ],
            config={
                "run_name": "replan_regenerate",
                "tags": ["replan", "llm"],
                "metadata": {
                    "task": state["task"],
                    "iteration": state["iterations"],
                    "replan_count": state.get("replan_count", 0),
                },
            },
        )
        response_text = llm.extract_text(response)
        new_subtasks = _parse_subtasks(response_text)

        if not new_subtasks:
            # 파싱 실패: plan_stale만 끄고 기존 계획 유지. 루프 라우터의 상한이
            # 무한 진입을 막는다.
            return {
                **state,
                "plan_stale": False,
                "replan_count": state.get("replan_count", 0) + 1,
            }

        return {
            **state,
            "subtasks": new_subtasks,
            "plan_stale": False,
            "subtask_start_iter": state["iterations"],
            "prev_active_subtask": -1,  # 다음 verify에서 새 active subtask로 재계산됨
            "replan_count": state.get("replan_count", 0) + 1,
            "error": None,
        }

    except KeyError as e:
        return {
            **state,
            "plan_stale": False,
            "replan_count": state.get("replan_count", 0) + 1,
            "error": f"[replan] 환경 변수 누락: {e}",
        }
    except Exception as e:
        return {
            **state,
            "plan_stale": False,
            "replan_count": state.get("replan_count", 0) + 1,
            "error": f"[replan] Unexpected error: {e}",
        }


def _compose_replan_input(state: AgentState) -> str:
    """replan 노드의 LLM 입력(HumanMessage 본문)을 조립한다.

    포함 항목:
        - 실행 컨텍스트(날짜)
        - 원 task
        - 기존 subtasks와 done 상태
        - 누적 memory
        - 최근 N 스텝 history (thought + action)
        - 현재 URL
        - DOM 텍스트 앞부분 (snippet)

    Args:
        state: 현재 에이전트 상태.

    Returns:
        LLM에 그대로 보낼 한글 문자열.
    """
    context_block = format_runtime_context_block()

    subtasks = state.get("subtasks", [])
    if subtasks:
        subtask_lines = []
        for i, t in enumerate(subtasks, 1):
            mark = "✅" if t.get("done") else "⬜"
            subtask_lines.append(f"{mark} {i}. {t.get('description', '')}")
        subtask_block = "\n".join(subtask_lines)
    else:
        subtask_block = "(없음)"

    memory = state.get("memory", "") or "(없음)"

    recent = state.get("history_items", [])[-_RECENT_HISTORY_FOR_REPLAN:]
    if recent:
        history_lines = []
        for item in recent:
            history_lines.append(
                f"#{item['step']} thought: {item.get('thought', '')}"
            )
            history_lines.append(
                f"     action:  {_compact_action(item.get('action', {}))}"
            )
        history_block = "\n".join(history_lines)
    else:
        history_block = "(아직 액션 없음)"

    dom_text = state.get("dom_text") or "(DOM 정보 없음)"
    dom_snippet = (
        dom_text[:_DOM_SNIPPET_CHARS] + "\n...(이하 생략)"
        if len(dom_text) > _DOM_SNIPPET_CHARS
        else dom_text
    )

    return (
        f"{context_block}\n\n"
        f"[원 목표]\n{state['task']}\n\n"
        f"[기존 계획과 진행 상태]\n{subtask_block}\n\n"
        f"[기억 메모]\n{memory}\n\n"
        f"[최근 액션]\n{history_block}\n\n"
        f"[현재 URL]\n{state.get('current_url', '(없음)')}\n\n"
        f"[현재 DOM 일부]\n{dom_snippet}"
    )


def _compact_action(action: dict[str, Any]) -> str:
    """history 표시용으로 액션 dict를 한 줄 JSON 문자열로 직렬화한다.

    Args:
        action: 액션 dict.

    Returns:
        직렬화된 문자열. 너무 길면 잘라낸다.
    """
    try:
        s = json.dumps(action, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(action)
    return s if len(s) <= 200 else s[:199] + "…"


__all__ = ["replan"]


# 외부 테스트에서 type 체크할 때 사용할 수 있도록 명시적으로 노출
_HistoryItem = HistoryItem  # noqa: F401
