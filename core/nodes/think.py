import base64
import json
import os
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import build_llm
from core.state import AgentState

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompt" / "agent.md"


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
        response = await llm.ainvoke(messages)
        response_text = response.content if isinstance(response.content, str) else str(response.content)

        parsed = _parse_response(response_text)
        if "error" in parsed:
            return {**state, "error": parsed["error"]}

        return {
            **state,
            "messages": list(state["messages"]) + [response],
            "last_action": json.dumps(parsed["action"], ensure_ascii=False),
            "is_done": parsed["is_done"],
            "result": parsed.get("result"),
            "error": None,
        }
    except KeyError as e:
        return {**state, "error": f"[think] 환경 변수 누락: {e}"}
    except Exception as e:
        return {**state, "error": f"[think] Unexpected error: {e}"}


def _build_messages(state: AgentState) -> list:
    """LLM에 전달할 메시지 리스트를 구성한다.

    시스템 프롬프트, 이전 대화 히스토리, 현재 관찰 결과(텍스트 + 이미지)를
    순서대로 포함한다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        SystemMessage와 HumanMessage로 구성된 메시지 리스트.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    extracted = state.get("extracted_result")
    extracted_section = f"\n\n[추출된 데이터]\n{extracted}" if extracted else ""

    content: list = [
        {
            "type": "text",
            "text": (
                f"목표: {state['task']}\n"
                f"현재 URL: {state['current_url']}\n\n"
                f"DOM 텍스트:\n{state['dom_text'] or '(없음)'}"
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
        *state["messages"],
        HumanMessage(content=content),
    ]


def _parse_response(response: str) -> dict:
    """LLM 응답 JSON을 파싱한다.

    Args:
        response: LLM이 반환한 순수 JSON 문자열

    Returns:
        파싱된 딕셔너리. 실패 시 {"error": "..."} 형태로 반환한다.
    """
    try:
        parsed = json.loads(response.strip())
    except json.JSONDecodeError as e:
        return {"error": f"[think] JSON 파싱 실패: {e} | 원문: {response[:200]}"}

    if parsed.get("is_done") and parsed.get("result") is None:
        return {"error": "[think] is_done이 true이면 result가 있어야 합니다."}

    if not isinstance(parsed.get("action"), dict):
        return {"error": "[think] action 필드가 객체가 아닙니다."}

    return parsed
