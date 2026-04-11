from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


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
