"""LLMAdapter - LLM 호출과 텍스트 추출을 통합하는 어댑터."""

from typing import Any

from langchain_core.messages import BaseMessage

from core.llm.base import BaseLLMProvider


class LLMAdapter:
    """LangChain BaseChatModel과 프로바이더별 텍스트 추출 로직을 통합한다.

    노드 코드가 프로바이더별 응답 형식을 알 필요 없이
    ainvoke()와 extract_text() 두 메서드만으로 LLM을 사용할 수 있게 한다.

    Attributes:
        _llm: 내부 LangChain LLM 인스턴스
        _provider: 텍스트 추출 로직을 제공하는 프로바이더 인스턴스
    """

    def __init__(self, provider: BaseLLMProvider) -> None:
        """LLMAdapter를 초기화한다.

        Args:
            provider: build()와 extract_text()를 구현한 프로바이더 인스턴스
        """
        self._provider = provider
        self._llm = provider.build()

    async def ainvoke(self, messages: list, config: dict[str, Any] | None = None) -> BaseMessage:
        """LLM을 비동기 호출한다.

        Args:
            messages: LangChain 메시지 리스트
            config: LangChain 런타임 설정 (run_name, tags, metadata 등)

        Returns:
            LLM이 반환한 AIMessage 인스턴스

        Raises:
            Exception: LLM 호출 실패 시 그대로 전파
        """
        return await self._llm.ainvoke(messages, config=config)

    def extract_text(self, response: BaseMessage) -> str:
        """프로바이더별 로직으로 응답에서 텍스트를 추출한다.

        Args:
            response: ainvoke()가 반환한 AIMessage 인스턴스

        Returns:
            추출된 텍스트 문자열
        """
        return self._provider.extract_text(response)
