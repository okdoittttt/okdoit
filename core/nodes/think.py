import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.context import format_runtime_context_block
from core.llm import build_llm
from core.state import AgentState, HistoryItem

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompt" / "agent.md"

# ── 컴팩션 상수 ──────────────────────────────────────────────────────────────
# 프롬프트에 원본으로 노출할 최근 스텝 개수. 이보다 오래된 스텝은 memory 블록에
# LLM 자신이 남긴 memory_update로 간접 유지된다.
KEEP_LAST_ITEMS: int = 5
# history_items의 thought 필드를 프롬프트에 노출할 때 사용하는 최대 길이.
MAX_THOUGHT_CHARS: int = 200
# 단일 액션 JSON 직렬화 결과의 최대 노출 길이.
MAX_ACTION_STR_CHARS: int = 200
# memory 누적값의 하드 상한. LLM이 매번 덮어쓰므로 기본 범위는 자유지만
# 프롬프트 폭주를 막기 위한 방어선.
MAX_MEMORY_CHARS: int = 1200


async def think(state: AgentState) -> AgentState:
    """현재 state를 보고 LLM을 호출해서 다음 액션을 결정한다.

    The Loop의 두 번째 노드. observe 노드가 수집한 스크린샷과 DOM 텍스트를
    LLM에 전달하고, 응답을 파싱해서 state를 업데이트한다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        messages, last_action, is_done, result이 업데이트된 AgentState.
        에러 발생 시 error 필드에 메시지를 기록하고 반환한다.
    """
    try:
        llm = build_llm()
        messages = _build_messages(state)
        response = await llm.ainvoke(
            messages,
            config={
                "run_name": "think_decide_action",
                "tags": ["think", "llm"],
                "metadata": {
                    "task": state["task"],
                    "iteration": state["iterations"],
                    "current_url": state.get("current_url", ""),
                },
            },
        )
        response_text = llm.extract_text(response)

        parsed = _parse_response(response_text)
        if "error" in parsed:
            return {**state, "error": parsed["error"]}

        updated_subtasks = _apply_step_done(state.get("subtasks", []), parsed.get("step_done", False))

        new_memory = _update_memory(state.get("memory", ""), parsed.get("memory_update"))
        new_history = _append_history_item(state, parsed)

        return {
            **state,
            "messages": list(state["messages"]) + [response],
            "last_action": json.dumps(parsed["action"], ensure_ascii=False),
            "is_done": parsed["is_done"],
            "result": parsed.get("result"),
            "subtasks": updated_subtasks,
            "memory": new_memory,
            "history_items": new_history,
            "last_action_error": None,
            "error": None,
        }
    except KeyError as e:
        return {**state, "error": f"[think] 환경 변수 누락: {e}"}
    except Exception as e:
        return {**state, "error": f"[think] Unexpected error: {e}"}


def _build_messages(state: AgentState) -> list:
    """LLM에 전달할 컴팩션된 메시지 리스트를 구성한다.

    SystemMessage 1개 + HumanMessage 1개로 고정한다. 과거 LLM 응답(state["messages"])
    은 LLM 입력에 직접 포함시키지 않는다. 대신 다음 두 수단으로 맥락을 보존한다.

        - history_items: 최근 KEEP_LAST_ITEMS개 스텝의 (thought, action) 요약
        - memory: LLM 스스로 매 턴 갱신하는 누적 메모 (오래된 스텝이 사라져도 유지)

    스크린샷도 현재 턴의 파일 하나만 base64로 실어 보낸다. 히스토리 스크린샷은
    포함하지 않는다.

    Args:
        state: 현재 에이전트 상태.

    Returns:
        [SystemMessage, HumanMessage]. 스크린샷이 없으면 HumanMessage content는
        text 블록 1개만 갖는다.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    context_block = format_runtime_context_block()

    subtasks = state.get("subtasks", [])
    plan_section = f"\n\n{_format_plan(subtasks)}" if subtasks else ""

    memory = state.get("memory", "")
    memory_section = f"\n\n[기억 메모]\n{memory}" if memory else ""

    history_section = _format_history_block(state.get("history_items", []))

    last_error = state.get("last_action_error")
    error_section = (
        f"\n\n[이전 액션 오류]\n{last_error}\n→ 다른 방법으로 동일한 목표를 달성하세요."
        if last_error else ""
    )

    extracted = state.get("extracted_result")
    extracted_section = f"\n\n[추출된 데이터]\n{extracted}" if extracted else ""

    content: list = [
        {
            "type": "text",
            "text": (
                f"{context_block}\n\n"
                f"목표: {state['task']}\n"
                f"현재 URL: {state['current_url']}"
                f"{plan_section}"
                f"{memory_section}"
                f"{history_section}"
                f"{error_section}"
                f"\n\nDOM 텍스트:\n{state['dom_text'] or '(없음)'}"
                f"{extracted_section}"
            ),
        }
    ]

    screenshot_path = state.get("screenshot_path")
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_data}"},
        })

    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=content),
    ]


def _format_history_block(history: list[HistoryItem]) -> str:
    """최근 KEEP_LAST_ITEMS개 history_items를 텍스트 블록으로 포맷한다.

    초과분이 있으면 '앞선 X개 스텝 생략' 헤더로 알린다. 압축된 스텝의
    상세 내용은 memory 블록으로 간접 유지된다.

    Args:
        history: state["history_items"] 리스트.

    Returns:
        "[최근 액션]" 섹션 문자열. history가 비면 빈 문자열.
    """
    if not history:
        return ""

    recent = history[-KEEP_LAST_ITEMS:]
    omitted = len(history) - len(recent)

    lines: list[str] = ["", "", "[최근 액션]"]
    if omitted > 0:
        lines.append(f"(앞선 {omitted}개 스텝 생략 — 핵심은 [기억 메모] 참고)")
    for item in recent:
        step_label = f"#{item['step']}"
        thought = _truncate(str(item.get("thought", "")), MAX_THOUGHT_CHARS)
        action_str = _compact_action(item.get("action", {}) or {})
        lines.append(f"{step_label} thought: {thought}")
        lines.append(f"     action:  {action_str}")
    return "\n".join(lines)


def _compact_action(action: dict[str, Any]) -> str:
    """액션 dict를 한 줄 JSON 문자열로 직렬화한다. 과도하게 길면 truncate.

    Args:
        action: 액션 dict.

    Returns:
        직렬화된 문자열. 직렬화 실패 시 str(action).
    """
    try:
        serialized = json.dumps(action, ensure_ascii=False)
    except (TypeError, ValueError):
        serialized = str(action)
    return _truncate(serialized, MAX_ACTION_STR_CHARS)


def _truncate(text: str, limit: int) -> str:
    """문자열을 limit 자 이하로 자르고 필요 시 말줄임표를 붙인다.

    Args:
        text: 원본 문자열.
        limit: 최대 길이. 1 이상.

    Returns:
        len(text) <= limit면 원본. 초과 시 limit-1자 + "…".
    """
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _append_history_item(state: AgentState, parsed: dict[str, Any]) -> list[HistoryItem]:
    """think가 방금 파싱한 응답을 history_items에 append한다.

    원본 history_items는 변경하지 않고 새 리스트를 반환한다.

    Args:
        state: 현재 상태.
        parsed: _parse_response 성공 결과.

    Returns:
        새 HistoryItem이 추가된 history_items 복사본.
    """
    raw_action = parsed.get("action")
    action: dict[str, Any] = raw_action if isinstance(raw_action, dict) else {}
    memory_update = parsed.get("memory_update")
    if memory_update is not None and not isinstance(memory_update, str):
        memory_update = str(memory_update)
    item: HistoryItem = {
        "step": state["iterations"],
        "thought": _truncate(str(parsed.get("thought", "")), MAX_THOUGHT_CHARS),
        "action": action,
        "memory_update": memory_update or None,
    }
    return list(state.get("history_items", [])) + [item]


def _update_memory(prev: str, memory_update: Optional[Any]) -> str:
    """memory_update로 누적 메모를 덮어쓴다.

    LLM이 매 턴 "현재까지의 요약"을 새로 쓰는 방식으로 동작한다. 빈 값이거나
    None이면 이전 값을 유지한다. 항상 MAX_MEMORY_CHARS로 제한한다.

    Args:
        prev: 이전 memory 문자열.
        memory_update: LLM이 제공한 새 memory 후보.

    Returns:
        갱신된 memory 문자열.
    """
    if memory_update is None:
        return prev
    if not isinstance(memory_update, str):
        memory_update = str(memory_update)
    stripped = memory_update.strip()
    if not stripped:
        return prev
    return _truncate(stripped, MAX_MEMORY_CHARS)


def _format_plan(subtasks: list[dict]) -> str:
    """subtasks 목록을 진행 상태가 표시된 문자열로 포맷한다.

    완료된 단계는 ✅, 현재 진행 중인 첫 번째 미완료 단계는 ▶, 나머지는 ⬜로 표시한다.

    Args:
        subtasks: [{"description": str, "done": bool}, ...] 형태의 목록

    Returns:
        포맷된 계획 문자열. subtasks가 비어있으면 빈 문자열.
    """
    if not subtasks:
        return ""

    current_marked = False
    lines = ["[작업 계획]"]
    for i, task in enumerate(subtasks, 1):
        if task["done"]:
            icon = "✅"
        elif not current_marked:
            icon = "▶"
            current_marked = True
        else:
            icon = "⬜"
        suffix = "  (현재)" if icon == "▶" else ""
        lines.append(f"{icon} {i}. {task['description']}{suffix}")
    return "\n".join(lines)


def _apply_step_done(subtasks: list[dict], step_done: bool) -> list[dict]:
    """step_done이 True이면 첫 번째 미완료 단계를 완료 처리한 새 목록을 반환한다.

    원본 subtasks는 변경하지 않는다.

    Args:
        subtasks: 현재 단계 목록
        step_done: think 노드 LLM 응답의 step_done 값

    Returns:
        업데이트된 subtasks 복사본.
    """
    if not step_done:
        return subtasks

    updated = [dict(t) for t in subtasks]
    for task in updated:
        if not task["done"]:
            task["done"] = True
            break
    return updated


def _strip_code_fence(text: str) -> str:
    """마크다운 코드 펜스(```json ... ```)를 제거하고 내부 텍스트만 반환한다.

    일부 LLM이 JSON 앞뒤에 코드 펜스를 붙이는 경우를 처리한다.

    Args:
        text: LLM 원본 응답 문자열

    Returns:
        코드 펜스가 제거된 문자열. 펜스가 없으면 그대로 반환한다.
    """
    match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text.strip(), re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _parse_response(response: str) -> dict:
    """LLM 응답 JSON을 파싱한다.

    Args:
        response: LLM이 반환한 JSON 문자열 (마크다운 펜스 포함 가능)

    Returns:
        파싱된 딕셔너리. 실패 시 {"error": "..."} 형태로 반환한다.
    """
    try:
        parsed = json.loads(_strip_code_fence(response))
    except json.JSONDecodeError as e:
        return {"error": f"[think] JSON 파싱 실패: {e} | 원문: {response[:200]}"}

    if parsed.get("is_done") and parsed.get("result") is None:
        return {"error": "[think] is_done이 true이면 result가 있어야 합니다."}

    if not isinstance(parsed.get("action"), dict):
        return {"error": "[think] action 필드가 객체가 아닙니다."}

    return parsed
