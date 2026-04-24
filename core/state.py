from typing import Optional, Any
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


class HistoryItem(TypedDict):
    """한 스텝에서 think 노드가 생성한 경량 요약 항목.

    원본 messages(감사 로그)와 별개로, 프롬프트 컴팩션에 사용된다.
    think 노드가 매 턴 응답을 파싱한 직후 append하고, _build_messages가
    최근 몇 개만 선별해 텍스트 블록으로 포맷한다.

    Attributes:
        step: 해당 스텝의 iteration 번호.
        thought: LLM 응답의 thought 필드. 길면 truncate됨.
        action: LLM이 결정한 액션 dict.
        memory_update: LLM이 해당 턴에 남긴 memory_update 문자열. 없으면 None.
    """
    step: int
    thought: str
    action: dict[str, Any]
    memory_update: Optional[str]


class AgentState(TypedDict):
    """The Loop 전체에서 공유되는 에이전트 상태.

    Attributes:
        task (str): 사용자의 원래 목표
        messages (list[BaseMessage]): LLM 원본 응답 누적(감사/디버깅용).
            LLM 입력에는 더 이상 그대로 포함되지 않는다. 대신 history_items와
            memory가 컴팩션된 형태로 프롬프트에 실린다.
        current_url (str): 현재 브라우저 URL
        screenshot_path (Optional[str]): 최신 스크린샷 저장 경로
        dom_text (Optional[str]): 최신 DOM 텍스트 트리
        last_action (Optional[str]): 직전 실행 액션
        is_done (bool): 루프 종료 여부
        result (Optional[str]): 최종 결과 메시지
        error (Optional[str]): 에러 메시지
        iterations (int): 현재 반복 횟수
        task_progress (dict): 작업 진전도 추적
            - total_steps: 예상되는 전체 단계 수
            - completed_steps: 완료된 단계 수
            - current_step: 현재 진행 중인 단계
            - step_info: 각 단계별 상세 정보
        collected_data (dict): 수집한 정보 누적
            - key: 정보 식별자 (예: "부산", "서울")
            - value: {"information": str, "collected": bool}
        subtasks (list[dict]): plan 노드가 분해한 작업 단계 목록
            - description: 단계 설명 문자열
            - done: 완료 여부
        consecutive_errors (int): 연속으로 발생한 에러 횟수. 성공 시 0으로 리셋된다.
        last_action_error (Optional[str]): LLM에게 전달할 직전 액션의 에러 메시지.
        memory (str): LLM이 턴마다 덮어쓰는 누적 요약 메모.
            오래된 스텝이 프롬프트에서 제거돼도 핵심 컨텍스트를 보존한다.
        history_items (list[HistoryItem]): think 노드가 매 턴 append하는 경량 요약.
            프롬프트 빌드 시 최근 KEEP_LAST_ITEMS개만 노출된다.
    """

    task: str
    messages: list[BaseMessage]
    current_url: str
    screenshot_path: Optional[str]
    dom_text: Optional[str]
    last_action: Optional[str]
    is_done: bool
    result: Optional[str]
    error: Optional[str]
    iterations: int
    task_progress: dict[str, Any]
    collected_data: dict[str, dict[str, Any]]
    extracted_result: Optional[str]
    subtasks: list[dict[str, Any]]
    consecutive_errors: int
    last_action_error: Optional[str]
    memory: str
    history_items: list[HistoryItem]