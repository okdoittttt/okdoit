import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from core.llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API 프로바이더.

    필수 환경변수:
        OPENAI_API_KEY: OpenAI API 키
        LLM_MODEL: 사용할 모델명 (예: gpt-4o, gpt-4o-mini)
    """

    def build(self) -> BaseChatModel:
        """ChatOpenAI 인스턴스를 생성해서 반환한다.

        Returns:
            설정된 ChatOpenAI 인스턴스

        Raises:
            KeyError: LLM_MODEL 환경변수가 없을 때
        """
        return ChatOpenAI(model=os.environ["LLM_MODEL"])
