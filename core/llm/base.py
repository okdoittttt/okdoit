from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


class BaseLLMProvider(ABC):
    """LLM 프로바이더 추상 기반 클래스.

    새 프로바이더를 추가할 때 이 클래스를 상속하고
    build() 메서드를 구현한다.
    """

    @abstractmethod
    def build(self) -> BaseChatModel:
        """LLM 인스턴스를 생성해서 반환한다.

        Returns:
            설정된 LangChain BaseChatModel 인스턴스
        """

    def extract_text(self, response: BaseMessage) -> str:
        """LLM 응답 메시지에서 텍스트를 추출한다.

        기본 구현은 str 응답과 list 응답(thinking mode)을 처리한다.
        프로바이더별로 다른 동작이 필요하면 이 메서드를 오버라이드한다.

        Args:
            response: LLM이 반환한 AIMessage 인스턴스

        Returns:
            추출된 텍스트 문자열
        """
        if isinstance(response.content, str):
            return response.content
        if isinstance(response.content, list):
            return next(
                (
                    block["text"]
                    for block in response.content
                    if isinstance(block, dict) and block.get("type") == "text"
                ),
                str(response.content),
            )
        return str(response.content)
