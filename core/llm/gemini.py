import os

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from core.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API 프로바이더.

    필수 환경변수:
        GOOGLE_API_KEY: Google AI Studio API 키
        LLM_MODEL: 사용할 모델명 (예: gemini-2.0-flash, gemini-2.5-pro)
    """

    def build(self) -> BaseChatModel:
        """ChatGoogleGenerativeAI 인스턴스를 생성해서 반환한다.

        Returns:
            설정된 ChatGoogleGenerativeAI 인스턴스

        Raises:
            KeyError: LLM_MODEL 환경변수가 없을 때
        """
        return ChatGoogleGenerativeAI(model=os.environ["LLM_MODEL"])
