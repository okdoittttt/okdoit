-- okdoit local-first storage schema v1.
--
-- 초기 부트스트랩에서 한 번 실행된다. 이후 누적 변경은 ``migrations.py`` 가 담당.
-- 모든 ``CREATE`` 는 ``IF NOT EXISTS`` 라 idempotent — 재시작/재설치에서도 안전.
--
-- PRAGMA(WAL, foreign_keys 등)는 ``connection`` 단위 설정이라 여기에 박지 않는다.
-- ``storage/db.py:open_connection`` 이 connection 마다 적용한다.

CREATE TABLE IF NOT EXISTS sessions (
  id              TEXT PRIMARY KEY,
  task            TEXT NOT NULL,
  status          TEXT NOT NULL,
  iterations      INTEGER NOT NULL DEFAULT 0,
  result          TEXT,
  error           TEXT,
  headless        INTEGER NOT NULL DEFAULT 1,
  llm_provider    TEXT,
  llm_model       TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  finished_at     TEXT,
  -- 미래 클라우드 동기화(B안) 자리 — v1 에서는 NULL 로만 존재.
  synced_at       TEXT,
  cloud_id        TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS events (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  type            TEXT NOT NULL,
  ts              TEXT NOT NULL,
  payload         TEXT NOT NULL,
  seq             INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, ts);

CREATE TABLE IF NOT EXISTS screenshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  path            TEXT NOT NULL,
  step_index      INTEGER,
  ts              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_screenshots_session ON screenshots(session_id);

CREATE TABLE IF NOT EXISTS artifacts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,
  data            TEXT NOT NULL,
  ts              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id);
