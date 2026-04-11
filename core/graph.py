from langgraph.graph import END, START, StateGraph

from core.nodes.act import act
from core.nodes.observe import observe
from core.nodes.think import think
from core.nodes.verify import verify
from core.state import AgentState


def create_graph():
    """StateGraph를 생성하고 컴파일해서 반환한다.

    노드 구성:
        observe → think → act → verify → (조건부) observe 또는 END

    Returns:
        컴파일된 LangGraph CompiledGraph
    """
    graph = StateGraph(AgentState)

    graph.add_node("observe", observe)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.add_node("verify", verify)

    graph.add_edge(START, "observe")
    graph.add_edge("observe", "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", "verify")
    graph.add_conditional_edges("verify", _should_continue)

    return graph.compile()


def _should_continue(state: AgentState) -> str:
    """verify 노드 이후 다음 노드를 결정한다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        루프를 종료할 경우 "__end__", 계속할 경우 "observe"
    """
    if state["is_done"] or state.get("error"):
        return END

    return "observe"


def initial_state(task: str) -> AgentState:
    """태스크를 받아서 초기 AgentState를 생성한다.

    Args:
        task: 사용자 입력 태스크

    Returns:
        모든 필드가 초기화된 AgentState
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
    )
