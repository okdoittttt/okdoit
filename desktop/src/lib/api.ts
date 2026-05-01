/**
 * sidecar REST 클라이언트.
 *
 * URL 베이스는 ``window.okdoit.sidecarUrl`` (preload 가 주입).
 */

import type { SessionArtifact } from "@/types/artifact";

export interface RunRequestBody {
  task: string;
  headless?: boolean;
}

export interface RunResponse {
  session_id: string;
}

/**
 * 새 작업 세션을 시작한다.
 *
 * @throws Error sidecar 가 4xx / 5xx 응답을 주거나 네트워크 실패 시.
 */
export async function postRun(body: RunRequestBody): Promise<RunResponse> {
  const url = `${window.okdoit.sidecarUrl}/run`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST /run 실패: ${res.status} ${detail}`);
  }
  return (await res.json()) as RunResponse;
}

// ── 세션 제어 ─────────────────────────────────────────────────

type SessionAction = "pause" | "resume" | "stop";

/**
 * 세션 제어 엔드포인트(``POST /sessions/{id}/{action}``)를 호출한다.
 *
 * @throws Error sidecar 가 4xx / 5xx 응답을 주거나 네트워크 실패 시.
 */
async function postSessionAction(
  sessionId: string,
  action: SessionAction,
): Promise<void> {
  const url = `${window.okdoit.sidecarUrl}/sessions/${sessionId}/${action}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST /sessions/${sessionId}/${action} 실패: ${res.status} ${detail}`);
  }
}

export const postPause = (sessionId: string): Promise<void> =>
  postSessionAction(sessionId, "pause");

export const postResume = (sessionId: string): Promise<void> =>
  postSessionAction(sessionId, "resume");

export const postStop = (sessionId: string): Promise<void> =>
  postSessionAction(sessionId, "stop");

// ── 아티팩트 ──────────────────────────────────────────────────

/**
 * 세션 아티팩트(결과 + 스크린샷 + 추출 데이터)를 조회한다.
 *
 * @throws Error sidecar 가 4xx / 5xx 응답을 주거나 네트워크 실패 시.
 */
export async function getArtifact(sessionId: string): Promise<SessionArtifact> {
  const url = `${window.okdoit.sidecarUrl}/sessions/${sessionId}/artifact`;
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`GET artifact 실패: ${res.status} ${detail}`);
  }
  return (await res.json()) as SessionArtifact;
}

/**
 * 정적 라우트 상대 경로를 절대 URL 로 변환한다.
 *
 * 예: ``"/static/screenshots/3_observe.png"`` → ``"http://127.0.0.1:8765/static/screenshots/3_observe.png"``.
 */
export function resolveSidecarUrl(relativePath: string): string {
  return `${window.okdoit.sidecarUrl}${relativePath}`;
}
