"""Repository 레이어 — SQL 캡슐화.

라우터 / 러너 / store 는 raw SQL 을 직접 만지지 않고 Repository 객체를 거친다.
각 Repository 는 sync ``sqlite3.Connection`` 을 받고 sync 메서드만 노출한다.
async 호출 측은 ``asyncio.to_thread`` 로 감싼다.
"""

from __future__ import annotations

from server.internal.storage.repositories.events import EventRepository
from server.internal.storage.repositories.screenshots import ScreenshotRepository
from server.internal.storage.repositories.sessions import SessionRepository

__all__ = ["EventRepository", "ScreenshotRepository", "SessionRepository"]
