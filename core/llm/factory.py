import os

from langchain_core.language_models import BaseChatModel

from core.llm.anthropic import AnthropicProvider
from core.llm.ollama import OllamaProvider

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


def build_llm() -> BaseChatModel:
    """LLM_PROVIDER 환경변수에 따라 LLM 인스턴스를 생성해서 반환한다.

    Returns:
        설정된 LLM 인스턴스

    Raises:
        KeyError: LLM_PROVIDER 또는 LLM_MODEL 환경변수가 없을 때
        ValueError: 지원하지 않는 LLM_PROVIDER일 때
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider not in _PROVIDERS:
        supported = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"지원하지 않는 LLM_PROVIDER: '{provider}'. 지원 목록: {supported}")

    return _PROVIDERS[provider]().build()
