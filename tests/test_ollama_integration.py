import os

import pytest
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from core.llm.factory import build_llm
from core.llm.ollama import OllamaProvider

load_dotenv()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: 실제 외부 서비스가 필요한 통합 테스트"
    )


@pytest.fixture(autouse=True)
def set_ollama_env(monkeypatch):
    """Ollama 환경변수를 설정한다."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    # Ollama 서버에 실제로 설치된 모델로 설정 (llama3.2가 아닌 경우 gemma4:e4b 사용)
    monkeypatch.setenv("LLM_MODEL", "gemma4:e4b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.mark.integration
def test_ollama_provider_build_returns_chat_ollama():
    """OllamaProvider.build()가 올바른 model/base_url로 ChatOllama를 반환하는지 확인한다."""
    from langchain_ollama import ChatOllama

    provider = OllamaProvider()
    llm = provider.build()

    assert isinstance(llm, ChatOllama)
    assert llm.model == os.environ["LLM_MODEL"]
    assert llm.base_url == os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.mark.integration
def test_factory_returns_ollama_when_provider_is_ollama():
    """LLM_PROVIDER=ollama일 때 build_llm()이 ChatOllama를 반환하는지 확인한다."""
    from langchain_ollama import ChatOllama

    llm = build_llm()
    assert isinstance(llm, ChatOllama)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ollama_responds_to_simple_prompt():
    """Ollama 서버에 실제 요청을 보내고 응답을 받는지 확인한다."""
    llm = build_llm()
    response = await llm.ainvoke([HumanMessage(content="'pong'이라고만 대답해.")])

    assert response.content is not None
    assert len(response.content) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ollama_responds_with_json():
    """Ollama가 JSON 형식 응답을 반환하는지 확인한다."""
    import json

    llm = build_llm()
    response = await llm.ainvoke([
        HumanMessage(content=(
            '다음 JSON 형식으로만 응답해. 다른 텍스트는 절대 포함하지 마.\n'
            '{"thought": "테스트 중", "action": "없음", "is_done": false, "result": null}'
        ))
    ])

    parsed = json.loads(response.content.strip())
    assert "thought" in parsed
    assert "action" in parsed
    assert "is_done" in parsed
    assert "result" in parsed
