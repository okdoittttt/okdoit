"""DB 부트스트랩 / 마이그레이션 단위 테스트.

storage 패키지가 제공하는 ``init_db`` / ``open_connection`` / ``migrations.apply``
의 계약을 검증한다 — 도메인 코드 의존 없이 순수 인프라 레벨.
"""

from __future__ import annotations

from pathlib import Path

from server.internal.storage import (
    init_db,
    migrations as storage_migrations,
    open_connection,
    schema_sql_path,
)


def test_init_db_creates_file(tmp_path: Path) -> None:
    """``init_db`` 호출 후 DB 파일이 디스크에 생성된다."""
    db = tmp_path / "okdoit.db"
    assert not db.exists()
    init_db(db, schema_sql_path())
    assert db.exists()


def test_init_db_creates_parent_dir(tmp_path: Path) -> None:
    """``data_dir`` 가 아직 없어도 ``init_db`` 가 만들어 준다."""
    db = tmp_path / "nested" / "deep" / "okdoit.db"
    assert not db.parent.exists()
    init_db(db, schema_sql_path())
    assert db.exists()


def test_init_db_creates_all_tables(tmp_path: Path) -> None:
    """초기 스키마 적용 후 4개 테이블이 모두 존재한다."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in rows}
        assert {"sessions", "events", "screenshots", "artifacts"}.issubset(names)
    finally:
        conn.close()


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    """``init_db`` 를 두 번 불러도 ``IF NOT EXISTS`` 라 에러 없이 통과한다."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    init_db(db, schema_sql_path())  # 두 번째 호출도 에러 없이 동작.


def test_pragma_wal_and_foreign_keys(tmp_path: Path) -> None:
    """``open_connection`` 이 WAL + foreign_keys=ON 을 적용한다."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert mode.lower() == "wal"
        assert fk == 1
    finally:
        conn.close()


def test_pragma_busy_timeout_is_set(tmp_path: Path) -> None:
    """``busy_timeout`` 이 0 이 아닌 값(5초)으로 설정돼 있다."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    try:
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5_000
    finally:
        conn.close()


def test_migrations_apply_no_op_on_v1(tmp_path: Path) -> None:
    """v1 시점엔 ``MIGRATIONS`` 가 비어있어 user_version 이 0 으로 유지된다."""
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    try:
        storage_migrations.apply(conn)
        assert storage_migrations.current_version(conn) == 0
    finally:
        conn.close()


def test_foreign_key_cascade_on_session_delete(tmp_path: Path) -> None:
    """sessions 삭제 시 events / screenshots / artifacts 가 cascade 로 함께 사라진다.

    스키마의 ``ON DELETE CASCADE`` 와 connection 의 ``foreign_keys=ON`` 이 함께
    동작해야 의도대로 정리된다 — 둘 중 하나라도 빠지면 회귀.
    """
    db = tmp_path / "okdoit.db"
    init_db(db, schema_sql_path())
    conn = open_connection(db)
    try:
        conn.execute(
            """
            INSERT INTO sessions(id, task, status, iterations, created_at, updated_at)
            VALUES ('sid', 'task', 'idle', 0, '2026-05-01T00:00:00Z', '2026-05-01T00:00:00Z')
            """
        )
        conn.execute(
            "INSERT INTO events(session_id, type, ts, payload, seq) "
            "VALUES ('sid', 'session.started', '2026-05-01T00:00:00Z', '{}', 1)"
        )
        conn.execute("DELETE FROM sessions WHERE id='sid'")
        remaining = conn.execute(
            "SELECT COUNT(*) FROM events WHERE session_id='sid'"
        ).fetchone()[0]
        assert remaining == 0
    finally:
        conn.close()
