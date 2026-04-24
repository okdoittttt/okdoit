"""LLM 프롬프트에 주입할 런타임 컨텍스트를 생성한다.

날짜, 타임존처럼 코드 안에서 계산되어야 하는 "현재 상태" 값을
프롬프트에서 사용할 수 있는 형태(dict/text)로 조립한다.
"""

from core.context.builder import build_runtime_context, format_runtime_context_block

__all__ = ["build_runtime_context", "format_runtime_context_block"]
