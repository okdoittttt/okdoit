/**
 * sidecar 의 ``GET /sessions/{id}/artifact`` 응답 타입.
 *
 * 원본은 ``server/internal/schemas/artifact.py`` 의 ``SessionArtifact``. 이 파일은
 * 수동 동기화로 유지한다(자동 생성은 추후 도입).
 */

import type { Subtask } from "@/types/events";
import type { SessionStatus } from "@/stores/sessionStore";

export interface CollectedDataEntry {
  /** 추출된 정보 본문(자유 형식 문자열). */
  information?: string;
  /** 백엔드가 저장한 추가 메타. */
  collected?: boolean;
  [key: string]: unknown;
}

export interface SessionArtifact {
  id: string;
  task: string;
  status: SessionStatus;
  iterations: number;
  result: string | null;
  error: string | null;
  subtasks: Subtask[];
  /** 정적 라우트 상대 경로 목록 (예: ``"/static/screenshots/3_observe.png"``). */
  screenshots: string[];
  /** 키는 사용자가 정한 식별자, 값은 ``information`` 등의 메타. */
  collected_data: Record<string, CollectedDataEntry>;
}
