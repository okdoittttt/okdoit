"""LangSmith 평가 실행 진입점.

think 노드를 데이터셋의 예제들에 대해 실행하고 점수를 집계한다.

Usage:
    # 구조 검사만 (빠름, API 비용 없음)
    python tests/eval/run_evals.py

    # LLM-as-judge 포함 전체 평가
    python tests/eval/run_evals.py --full

    # 실험 이름 지정 (기본값: think_node_eval)
    python tests/eval/run_evals.py --experiment-prefix think_v2
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from langsmith import Client, evaluate

load_dotenv()

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.nodes.think import think
from core.state import AgentState
from tests.eval.datasets import DATASET_NAME, seed_dataset
from tests.eval.evaluators import FULL_EVALUATORS, STRUCTURAL_EVALUATORS


def _build_state(inputs: dict) -> AgentState:
    """데이터셋 inputs를 AgentState로 변환한다.

    데이터셋에 없는 필드는 기본값으로 채운다.

    Args:
        inputs: 데이터셋 예제의 inputs 딕셔너리

    Returns:
        think 노드에 전달할 AgentState
    """
    return AgentState(
        task=inputs["task"],
        messages=inputs.get("messages", []),
        current_url=inputs.get("current_url", "about:blank"),
        screenshot_path=None,
        dom_text=inputs.get("dom_text", ""),
        last_action=None,
        is_done=False,
        result=None,
        error=None,
        iterations=inputs.get("iterations", 1),
        task_progress={},
        collected_data={},
        extracted_result=None,
        subtasks=inputs.get("subtasks", []),
        consecutive_errors=0,
        last_action_error=inputs.get("last_action_error"),
    )


def think_target(inputs: dict) -> dict:
    """평가 대상 함수. inputs를 받아 think 노드를 실행하고 출력을 반환한다.

    LangSmith evaluate()는 동기 함수를 기대하므로 asyncio.run()으로 감싼다.

    Args:
        inputs: 데이터셋 예제의 inputs 딕셔너리

    Returns:
        think 노드 출력 중 평가에 필요한 필드만 담은 딕셔너리
    """
    state = _build_state(inputs)
    result = asyncio.run(think(state))
    return {
        "last_action": result.get("last_action"),
        "is_done": result.get("is_done"),
        "result": result.get("result"),
        "error": result.get("error"),
    }


def _print_summary(eval_results) -> None:
    """평가 결과를 터미널에 출력한다.

    Args:
        eval_results: evaluate()가 반환한 결과 객체
    """
    print("\n" + "=" * 60)
    print("평가 결과 요약")
    print("=" * 60)

    try:
        results_df = eval_results.to_pandas()
        score_cols = [c for c in results_df.columns if c.startswith("feedback.")]
        for col in score_cols:
            metric = col.replace("feedback.", "")
            mean = results_df[col].mean()
            print(f"  {metric:<35} {mean:.2f}")
    except Exception:
        print("  (결과를 pandas로 변환할 수 없습니다. LangSmith UI에서 확인하세요.)")

    print("=" * 60)
    print(f"\nLangSmith UI: https://smith.langchain.com/")
    print(f"Project: {os.getenv('LANGCHAIN_PROJECT', 'default')}")


def main() -> None:
    """CLI 진입점. 인자를 파싱하고 평가를 실행한다."""
    parser = argparse.ArgumentParser(description="LangSmith think 노드 평가")
    parser.add_argument(
        "--full",
        action="store_true",
        help="LLM-as-judge 포함 전체 평가 실행 (API 비용 발생)",
    )
    parser.add_argument(
        "--experiment-prefix",
        default="think_node_eval",
        help="LangSmith 실험 이름 접두사 (기본값: think_node_eval)",
    )
    parser.add_argument(
        "--dataset",
        default=DATASET_NAME,
        help=f"평가할 데이터셋 이름 (기본값: {DATASET_NAME})",
    )
    args = parser.parse_args()

    client = Client()
    seed_dataset(client, args.dataset)

    evaluators = FULL_EVALUATORS if args.full else STRUCTURAL_EVALUATORS
    evaluator_names = [e.__name__ for e in evaluators]
    print(f"\n[eval] 데이터셋: {args.dataset}")
    print(f"[eval] 평가자: {evaluator_names}")
    print(f"[eval] 실험 접두사: {args.experiment_prefix}\n")

    results = evaluate(
        think_target,
        data=args.dataset,
        evaluators=evaluators,
        experiment_prefix=args.experiment_prefix,
        metadata={"node": "think", "mode": "full" if args.full else "structural"},
    )

    _print_summary(results)


if __name__ == "__main__":
    main()
