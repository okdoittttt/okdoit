from typing import Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """The Loop 전체에서 공유되는 에이전트 상태.

    Attributes:
        task (str): 사용자의 원래 목표
        messages (list[BaseMessage]): LLM 대화 히스토리
        current_url (str): 현재 브라우저 URL
        screenshot_path (Optional[str]): 최신 스크린샷 저장 경로
        dom_text (Optional[str]): 최신 DOM 텍스트 트리
        last_action (Optional[str]): 직전 실행 액션
        is_done (bool): 루프 종료 여부
        result (Optional[str]): 최종 결과 메시지
        error (Optional[str]): 에러 메시지
        iterations (int): 현재 반복 횟수
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