import os

from core.llm.adapter import LLMAdapter
from core.llm.anthropic import AnthropicProvider
from core.llm.gemini import GeminiProvider
from core.llm.ollama import OllamaProvider
from core.llm.openai import OpenAIProvider

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
}


def build_llm() -> LLMAdapter:
    """LLM_PROVIDER 환경변수에 따라 LLMAdapter 인스턴스를 생성해서 반환한다.

    Returns:
        설정된 LLMAdapter 인스턴스

    Raises:
        KeyError: LLM_PROVIDER 또는 LLM_MODEL 환경변수가 없을 때
        ValueError: 지원하지 않는 LLM_PROVIDER일 때
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider not in _PROVIDERS:
        supported = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"지원하지 않는 LLM_PROVIDER: '{provider}'. 지원 목록: {supported}")

    return LLMAdapter(_PROVIDERS[provider]())
