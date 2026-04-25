import argparse
import asyncio
import sys
import uuid

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

from core.browser import BrowserManager
from core.graph import create_graph, initial_state
from core.nodes.verify import MAX_LOOP_ITERATIONS
from core.state import AgentState


def main() -> None:
    """CLI 진입점. --task 인자를 파싱하고 그래프를 실행한다.

    Usage:
        python agent.py --task "내일 서울 날씨 알려줘"
        python agent.py --task "내일 서울 날씨 알려줘" --no-headless
    """
    parser = argparse.ArgumentParser(description="Web Agent CLI")
    parser.add_argument("--task", required=True, help="수행할 태스크")
    parser.add_argument("--no-headless", action="store_true", help="브라우저 UI 표시")
    args = parser.parse_args()

    load_dotenv()

    headless = not args.no_headless
    manager = BrowserManager(headless=headless)

    try:
        asyncio.run(_run(task=args.task, manager=manager))
    except KeyboardInterrupt:
        print("\n[중단] Ctrl+C 감지. 브라우저를 종료합니다.")
        asyncio.run(manager.stop())
        sys.exit(0)


async def _run(task: str, manager: BrowserManager) -> None:
    """그래프를 스트리밍으로 실행하고 매 스텝 결과를 출력한다.

    Args:
        task: 수행할 태스크 문자열
        manager: 초기화된 BrowserManager 인스턴스
    """
    await manager.start()

    try:
        graph = create_graph()
        state = initial_state(task)
        final: AgentState = state

        session_id = str(uuid.uuid4())
        run_config = RunnableConfig(
            run_name="okdoit_agent_run",
            tags=["agent"],
            metadata={"task": task, "session_id": session_id},
        )

        print(f"\n[태스크] {task}\n{'─' * 60}")

        async for step in graph.astream(state, config=run_config):
            for node_name, node_state in step.items():
                final = node_state
                _print_step(node_name, node_state)

        print('─' * 60)
        if final.get("error"):
            print(f"[Error]        {final['error']}")
        else:
            print(f"[Success]      {final.get('result', '(결과 없음)')}")

    finally:
        await manager.stop()


def _print_step(node_name: str, state: AgentState) -> None:
    """노드 실행 결과를 터미널에 출력한다.

    Args:
        node_name: 실행된 노드 이름
        state: 해당 노드가 반환한 AgentState
    """
    if node_name == "think":
        history = state.get("history_items", [])
        thought = history[-1]["thought"] if history else ""
        print(f"[Thought]      {thought}")
        if not state.get("is_done"):
            print(f"[Action]       {state.get('last_action', '')}")

    elif node_name == "observe":
        dom = state.get("dom_text") or ""
        print(f"[Observation]  {dom[:100].replace(chr(10), ' ')}")

    elif node_name == "verify":
        print(f"[Verify]       반복 {state.get('iterations', 0)}회 / 최대 {MAX_LOOP_ITERATIONS}회")
        plan_summary = _format_plan_summary(state.get("subtasks", []))
        if plan_summary:
            print(f"[Plan]         {plan_summary}")


def _format_plan_summary(subtasks: list) -> str:
    """subtasks를 한 줄 요약 문자열로 포맷한다.

    Args:
        subtasks: [{"description": str, "done": bool}, ...] 형태의 목록

    Returns:
        "✅ 1.단계1  ▶ 2.단계2  ⬜ 3.단계3" 형태의 문자열. 비어있으면 빈 문자열.
    """
    if not subtasks:
        return ""

    parts = []
    current_marked = False
    for i, task in enumerate(subtasks, 1):
        short = task["description"][:12] + ("…" if len(task["description"]) > 12 else "")
        if task["done"]:
            parts.append(f"✅ {i}.{short}")
        elif not current_marked:
            parts.append(f"▶ {i}.{short}")
            current_marked = True
        else:
            parts.append(f"⬜ {i}.{short}")
    return "  ".join(parts)


if __name__ == "__main__":
    main()
