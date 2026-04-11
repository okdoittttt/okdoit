import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from core.llm.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API 프로바이더.

    필수 환경변수:
        ANTHROPIC_API_KEY: Anthropic API 키
        LLM_MODEL: 사용할 모델명 (예: claude-sonnet-4-6)
    """

    def build(self) -> BaseChatModel:
        """ChatAnthropic 인스턴스를 생성해서 반환한다.

        Returns:
            설정된 ChatAnthropic 인스턴스

        Raises:
            KeyError: LLM_MODEL 환경변수가 없을 때
        """
        return ChatAnthropic(model=os.environ["LLM_MODEL"])
