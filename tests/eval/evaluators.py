"""LangSmith 평가자(evaluator) 모음.

각 평가자는 (run, example) → {"key": str, "score": float} 형태를 반환한다.
score 1.0 = 통과, 0.0 = 실패.
"""

import json
from typing import Optional

from langsmith.schemas import Example, Run

# ── 규칙 기반 평가자 ──────────────────────────────────────────────────────────


def action_json_valid(run: Run, example: Example) -> dict:
    """think 노드 출력의 action 필드가 유효한 JSON 객체인지 검사한다.

    type 필드가 존재하는 dict 여부를 확인한다.
    LLM 호출 없이 구조만 검증하므로 빠르고 비용이 없다.

    Args:
        run: LangSmith 실행 결과
        example: 데이터셋 예제

    Returns:
        key="action_json_valid", score=1.0(통과) or 0.0(실패)
    """
    last_action: Optional[str] = (run.outputs or {}).get("last_action")

    if not last_action:
        return {"key": "action_json_valid", "score": 0.0, "comment": "last_action 없음"}

    try:
        action = json.loads(last_action)
        is_valid = isinstance(action, dict) and "type" in action
    except json.JSONDecodeError:
        return {"key": "action_json_valid", "score": 0.0, "comment": "JSON 파싱 실패"}

    return {
        "key": "action_json_valid",
        "score": 1.0 if is_valid else 0.0,
        "comment": f"action type: {action.get('type', '없음')}",
    }


def done_requires_result(run: Run, example: Example) -> dict:
    """is_done=True인 경우 result 필드가 반드시 존재해야 한다는 규칙을 검사한다.

    is_done=False 이면 항상 통과(N/A).

    Args:
        run: LangSmith 실행 결과
        example: 데이터셋 예제

    Returns:
        key="done_requires_result", score=1.0(통과) or 0.0(실패)
    """
    outputs = run.outputs or {}
    is_done: bool = outputs.get("is_done", False)

    if not is_done:
        return {"key": "done_requires_result", "score": 1.0, "comment": "N/A (진행 중)"}

    result: Optional[str] = outputs.get("result")
    has_result = result is not None and result.strip() != ""

    return {
        "key": "done_requires_result",
        "score": 1.0 if has_result else 0.0,
        "comment": f"result: {result!r}",
    }


def action_type_matches_expected(run: Run, example: Example) -> dict:
    """실제 action type이 데이터셋에서 기대하는 type과 일치하는지 확인한다.

    example.outputs에 expected_action_type이 없으면 스킵(1.0).

    Args:
        run: LangSmith 실행 결과
        example: 데이터셋 예제 (outputs.expected_action_type 사용)

    Returns:
        key="action_type_matches", score=1.0(일치) or 0.0(불일치)
    """
    expected: Optional[str] = (example.outputs or {}).get("expected_action_type")
    if not expected:
        return {"key": "action_type_matches", "score": 1.0, "comment": "expected 없음, 스킵"}

    last_action: Optional[str] = (run.outputs or {}).get("last_action")
    if not last_action:
        return {"key": "action_type_matches", "score": 0.0, "comment": "last_action 없음"}

    try:
        action = json.loads(last_action)
        actual_type = action.get("type", "")
    except json.JSONDecodeError:
        return {"key": "action_type_matches", "score": 0.0, "comment": "JSON 파싱 실패"}

    match = actual_type == expected
    return {
        "key": "action_type_matches",
        "score": 1.0 if match else 0.0,
        "comment": f"expected={expected}, actual={actual_type}",
    }


# ── LLM-as-Judge 평가자 ──────────────────────────────────────────────────────

def action_appropriateness_judge(run: Run, example: Example) -> dict:
    """LLM을 심판으로 사용해 선택한 action이 상황에 적절한지 평가한다.

    DOM 상태와 목표를 보고 Claude가 0~1 점수를 매긴다.
    규칙 기반으로 판단하기 어려운 의미적 적절성을 평가할 때 사용한다.
    API 비용이 발생하므로 중요 케이스에 선택적으로 적용한다.

    Args:
        run: LangSmith 실행 결과
        example: 데이터셋 예제

    Returns:
        key="action_appropriateness", score=0.0~1.0
    """
    from core.llm import build_llm
    from langchain_core.messages import HumanMessage

    outputs = run.outputs or {}
    inputs = run.inputs or {}

    task = inputs.get("task", "")
    dom_text = inputs.get("dom_text", "")
    last_action = outputs.get("last_action", "")

    if not last_action:
        return {"key": "action_appropriateness", "score": 0.0, "comment": "last_action 없음"}

    prompt = f"""당신은 웹 자동화 에이전트의 행동을 평가하는 심판입니다.

[목표]
{task}

[현재 페이지 DOM]
{dom_text[:2000]}

[에이전트가 선택한 액션]
{last_action}

위 상황에서 이 액션이 목표 달성에 얼마나 적절한지 0에서 1 사이의 숫자만 답하세요.
0 = 전혀 부적절, 0.5 = 보통, 1 = 매우 적절
숫자 외에 아무것도 출력하지 마세요."""

    try:
        llm = build_llm()
        import asyncio
        response = asyncio.run(llm.ainvoke([HumanMessage(content=prompt)]))
        score = float(response.content.strip())
        score = max(0.0, min(1.0, score))
    except (ValueError, Exception) as e:
        return {"key": "action_appropriateness", "score": 0.0, "comment": f"평가 실패: {e}"}

    return {"key": "action_appropriateness", "score": score}


# ── 평가자 묶음 ──────────────────────────────────────────────────────────────

#: 빠른 회귀 테스트용. LLM 호출 없이 구조/규칙만 검사한다.
STRUCTURAL_EVALUATORS = [
    action_json_valid,
    done_requires_result,
    action_type_matches_expected,
]

#: 전체 품질 평가용. LLM-as-judge를 포함하므로 API 비용이 발생한다.
FULL_EVALUATORS = [
    *STRUCTURAL_EVALUATORS,
    action_appropriateness_judge,
]
