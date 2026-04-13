"""액션 모듈 - 브라우저 자동화 액션 정의 및 레지스트리."""

from core.actions._registry import ActionRegistry, registry

# 하단 임포트: 데코레이터 등록을 트리거하는 사이드이펙트
import core.actions.navigation  # noqa: F401, E402
import core.actions.interaction  # noqa: F401, E402

__all__ = ["ActionRegistry", "registry"]
