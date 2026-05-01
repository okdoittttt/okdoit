"""local-first storage 패키지.

``server.internal.storage`` 는 SQLite 영속화 인프라를 제공한다.
``db`` 모듈은 connection 팩토리 + 부트스트랩, ``migrations`` 는 ``PRAGMA user_version``
기반 마이그레이터. Repository (PR3 부터) 는 ``storage.repositories`` 하위에 둔다.
"""

from __future__ import annotations

from server.internal.storage import migrations
from server.internal.storage.db import init_db, open_connection, schema_sql_path

__all__ = ["init_db", "migrations", "open_connection", "schema_sql_path"]
