import os

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from core.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """로컬 Ollama 프로바이더.

    필수 환경변수:
        LLM_MODEL: 사용할 모델명 (예: llama3.2, gemma3)

    선택 환경변수:
        OLLAMA_BASE_URL: Ollama 서버 주소 (기본값: http://localhost:11434)
    """

    def build(self) -> BaseChatModel:
        """ChatOllama 인스턴스를 생성해서 반환한다.

        Returns:
            설정된 ChatOllama 인스턴스

        Raises:
            KeyError: LLM_MODEL 환경변수가 없을 때
        """
        return ChatOllama(
            model=os.environ["LLM_MODEL"],
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
