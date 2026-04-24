from langgraph.graph import END, START, StateGraph

from core.nodes.act import act
from core.nodes.observe import observe
from core.nodes.plan import plan
from core.nodes.replan import replan
from core.nodes.think import think
from core.nodes.verify import verify
from core.state import AgentState

# replan 노드 호출 누적 상한. 무한 replan 루프를 방지한다.
MAX_REPLANS: int = 3


def create_graph():
    """StateGraph를 생성하고 컴파일해서 반환한다.

    노드 구성:
        START → plan → observe → think → act → verify → {END | observe | replan}
                                                  │
                                                  └──(plan_stale)──▶ replan ──▶ observe

    plan은 시작 시 한 번만 실행되고, replan은 verify가 stuck 패턴이나
    plan_stale 신호를 감지했을 때 동적으로 진입한다.

    Returns:
        컴파일된 LangGraph CompiledGraph.
    """
    graph = StateGraph(AgentState)

    graph.add_node("plan", plan)
    graph.add_node("observe", observe)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.add_node("verify", verify)
    graph.add_node("replan", replan)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "observe")
    graph.add_edge("observe", "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", "verify")
    graph.add_conditional_edges("verify", _route_after_verify)
    graph.add_edge("replan", "observe")

    return graph.compile()


def _should_continue(state: AgentState) -> str:
    """레거시 라우터. is_done이면 종료, 아니면 observe로 계속.

    그래프 자체는 ``_route_after_verify`` 를 사용한다. 이 함수는 외부에서
    state 흐름을 단순 검사할 때를 위한 호환 API로 유지된다.

    Args:
        state: 현재 에이전트 상태.

    Returns:
        루프를 종료할 경우 END, 계속할 경우 "observe".
    """
    if state["is_done"]:
        return END

    return "observe"


def _route_after_verify(state: AgentState) -> str:
    """verify 이후 다음 노드를 결정한다.

    우선순위:
        1. is_done → END
        2. _should_replan → "replan"
        3. 그 외 → "observe"

    Args:
        state: 현재 에이전트 상태.

    Returns:
        다음 노드 이름 또는 END.
    """
    if state["is_done"]:
        return END
    if _should_replan(state):
        return "replan"
    return "observe"


def _should_replan(state: AgentState) -> bool:
    """replan 노드로 진입해야 할지 판단한다.

    조건 (어느 하나라도 참이면 replan):
        - state["plan_stale"] 가 True (think 또는 verify가 신호)
        - subtasks가 모두 done인데 is_done=False (계획이 부족했음)

    단, replan_count가 MAX_REPLANS 이상이면 더 이상 진입하지 않는다(루프 방지).

    Args:
        state: 현재 상태.

    Returns:
        replan으로 분기해야 하면 True.
    """
    if state.get("replan_count", 0) >= MAX_REPLANS:
        return False
    if state.get("plan_stale"):
        return True
    subtasks = state.get("subtasks", [])
    if subtasks and all(s.get("done") for s in subtasks) and not state["is_done"]:
        return True
    return False


def initial_state(task: str) -> AgentState:
    """태스크를 받아서 초기 AgentState를 생성한다.

    Args:
        task: 사용자 입력 태스크.

    Returns:
        모든 필드가 초기화된 AgentState.
    """
    return AgentState(
        task=task,
        messages=[],
        current_url="",
        screenshot_path=None,
        dom_text=None,
        last_action=None,
        is_done=False,
        result=None,
        error=None,
        iterations=0,
        task_progress={
            "total_steps": 0,
            "completed_steps": 0,
            "current_step": 0,
            "step_info": {},
        },
        collected_data={},
        extracted_result=None,
        subtasks=[],
        consecutive_errors=0,
        last_action_error=None,
        memory="",
        history_items=[],
        action_history=[],
        last_action_result=None,
        selector_map={},
        plan_stale=False,
        subtask_start_iter=0,
        prev_active_subtask=-1,
        replan_count=0,
    )
