/**
 * sidecar WebSocket 이벤트의 TypeScript 미러.
 *
 * 원본은 ``server/internal/events/`` 의 Pydantic 모델. 이 파일은 수동으로 동기화한다
 * (자동 생성은 추후 도입). 이벤트가 추가/변경되면 양쪽 모두 갱신해야 한다.
 *
 * 형식 결정:
 *   - 모든 이벤트는 ``type`` 리터럴로 판별되는 discriminated union 멤버.
 *   - 모든 이벤트는 공통으로 ``session_id`` 와 ``ts`` 를 가진다.
 *   - Python 의 snake_case 필드명을 그대로 유지(서버 JSON 그대로 매칭하기 위함).
 */

export interface BaseEvent {
  session_id: string;
  ts: string;
}

export interface Subtask {
  index: number;
  description: string;
  done: boolean;
}

// ── 세션 라이프사이클 ────────────────────────────────────────────

export interface SessionStarted extends BaseEvent {
  type: "session.started";
  task: string;
}

export interface SessionFinished extends BaseEvent {
  type: "session.finished";
  result: string | null;
  iterations: number;
}

export interface SessionErrored extends BaseEvent {
  type: "session.errored";
  error: string;
}

export interface SessionPaused extends BaseEvent {
  type: "session.paused";
}

export interface SessionResumed extends BaseEvent {
  type: "session.resumed";
}

export interface SessionStopped extends BaseEvent {
  type: "session.stopped";
}

// ── 그래프 진행 ─────────────────────────────────────────────────

export interface PlanCreated extends BaseEvent {
  type: "plan.created";
  subtasks: Subtask[];
}

export interface PlanReplanned extends BaseEvent {
  type: "plan.replanned";
  reason: string;
  replan_count: number;
  subtasks: Subtask[];
}

export interface SubtaskActivated extends BaseEvent {
  type: "subtask.activated";
  index: number;
  description: string;
}

// ── 노드별 단계 ────────────────────────────────────────────────

export interface StepThinking extends BaseEvent {
  type: "step.thinking";
  iteration: number;
  thought: string;
  action: Record<string, unknown>;
  memory_update: string | null;
}

export interface StepActed extends BaseEvent {
  type: "step.acted";
  iteration: number;
  action: string;
  success: boolean;
  error_code: string | null;
  error_message: string | null;
  extracted: unknown | null;
}

export interface StepObserved extends BaseEvent {
  type: "step.observed";
  iteration: number;
  current_url: string;
  screenshot_path: string | null;
  interactive_count: number;
}

export interface StepVerified extends BaseEvent {
  type: "step.verified";
  iteration: number;
  is_done: boolean;
  consecutive_errors: number;
}

// ── 합집합 ─────────────────────────────────────────────────────

export type ServerEvent =
  | SessionStarted
  | SessionFinished
  | SessionErrored
  | SessionPaused
  | SessionResumed
  | SessionStopped
  | PlanCreated
  | PlanReplanned
  | SubtaskActivated
  | StepThinking
  | StepActed
  | StepObserved
  | StepVerified;

export type ServerEventType = ServerEvent["type"];
