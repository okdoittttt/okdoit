/**
 * 세션 화면 상태를 관리하는 Zustand 스토어.
 *
 * 이벤트 적용 로직(``reduceEvent``)은 순수 함수로 분리해 단위 테스트가 쉽다.
 * 스토어 자체는 (a) 새 세션 시작, (b) 이벤트 적용, (c) 리셋 액션을 노출한다.
 *
 * v0.1 은 단일 세션만 다룬다. 멀티세션 지원(`SessionList`)은 v0.3.
 */

import { create } from "zustand";
import type { ServerEvent, Subtask } from "@/types/events";

// ── 도메인 타입 ────────────────────────────────────────────────

export type SessionStatus =
  | "idle"
  | "running"
  | "paused"
  | "finished"
  | "errored"
  | "stopped";

export type StepKind = "thinking" | "acted" | "observed" | "verified";

export interface StepEntry {
  /** ts 와 함께 정렬 키로 쓰이는 단조 증가 ID. */
  id: number;
  iteration: number;
  kind: StepKind;
  /** 화면에 한 줄로 보여줄 요약 텍스트. */
  summary: string;
  /** 원본 페이로드(상세 펼치기 용). */
  payload: ServerEvent;
}

export interface SessionState {
  sessionId: string | null;
  task: string | null;
  status: SessionStatus;
  subtasks: Subtask[];
  /** ``-1`` 은 active subtask 미정. */
  activeSubtaskIndex: number;
  steps: StepEntry[];
  /** plan.replanned 직후 잠깐 강조 표시할지 여부. UI 가 자동으로 끈다. */
  replanFlash: boolean;
  result: string | null;
  error: string | null;
  iterations: number;

  // ── 액션 ──
  startSession: (sessionId: string, task: string) => void;
  applyEvent: (event: ServerEvent) => void;
  clearReplanFlash: () => void;
  reset: () => void;
}

const INITIAL: Omit<
  SessionState,
  "startSession" | "applyEvent" | "clearReplanFlash" | "reset"
> = {
  sessionId: null,
  task: null,
  status: "idle",
  subtasks: [],
  activeSubtaskIndex: -1,
  steps: [],
  replanFlash: false,
  result: null,
  error: null,
  iterations: 0,
};

// ── reducer (순수 함수) ────────────────────────────────────────

let nextStepId = 1;

/**
 * ``ServerEvent`` 를 받아 state 를 변환한다. 부수효과 없음(zustand set 함수가 호출).
 *
 * 새 이벤트 타입이 생기면 여기에 case 한 줄을 추가하면 된다.
 */
export function reduceEvent(state: SessionState, event: ServerEvent): Partial<SessionState> {
  switch (event.type) {
    case "session.started":
      return { status: "running", task: event.task };

    case "session.finished":
      return {
        status: "finished",
        result: event.result,
        iterations: event.iterations,
      };

    case "session.errored":
      return { status: "errored", error: event.error };

    case "session.paused":
      return { status: "paused" };

    case "session.resumed":
      return { status: "running" };

    case "session.stopped":
      return { status: "stopped" };

    case "plan.created":
      return { subtasks: event.subtasks, activeSubtaskIndex: 0 };

    case "plan.replanned":
      return {
        subtasks: event.subtasks,
        activeSubtaskIndex: 0,
        replanFlash: true,
      };

    case "subtask.activated":
      return { activeSubtaskIndex: event.index };

    case "step.thinking":
      return {
        steps: [...state.steps, makeStep(event, "thinking", thinkingSummary(event))],
        iterations: event.iteration,
      };

    case "step.acted":
      return {
        steps: [...state.steps, makeStep(event, "acted", actedSummary(event))],
        iterations: event.iteration,
      };

    case "step.observed":
      return {
        steps: [...state.steps, makeStep(event, "observed", observedSummary(event))],
        iterations: event.iteration,
      };

    case "step.verified":
      return {
        steps: [...state.steps, makeStep(event, "verified", verifiedSummary(event))],
        iterations: event.iteration,
      };
  }
}

// ── 요약 포매터 ────────────────────────────────────────────────

function makeStep(
  event: ServerEvent,
  kind: StepKind,
  summary: string,
): StepEntry {
  // step.* 만 makeStep 으로 들어오므로 ``iteration`` 이 존재한다.
  const iteration = (event as { iteration: number }).iteration;
  return { id: nextStepId++, iteration, kind, summary, payload: event };
}

function thinkingSummary(e: { thought: string; action: Record<string, unknown> }): string {
  const actionName = typeof e.action.name === "string" ? e.action.name : "?";
  const thought = e.thought.length > 80 ? `${e.thought.slice(0, 80)}…` : e.thought;
  return `${thought}  →  ${actionName}`;
}

function actedSummary(e: { action: string; success: boolean; error_message: string | null }): string {
  if (e.success) return `✓ ${e.action}`;
  return `✗ ${e.action} — ${e.error_message ?? "(원인 불명)"}`;
}

function observedSummary(e: { current_url: string; interactive_count: number }): string {
  const url = e.current_url || "(빈 페이지)";
  return `${url}  ·  요소 ${e.interactive_count}개`;
}

function verifiedSummary(e: { is_done: boolean; consecutive_errors: number }): string {
  if (e.is_done) return "종료 판정";
  if (e.consecutive_errors > 0) return `계속 (연속 에러 ${e.consecutive_errors})`;
  return "계속";
}

// ── 스토어 ────────────────────────────────────────────────────

export const useSession = create<SessionState>((set) => ({
  ...INITIAL,

  startSession: (sessionId, task) =>
    set({ ...INITIAL, sessionId, task, status: "running" }),

  applyEvent: (event) => set((s) => reduceEvent(s, event)),

  clearReplanFlash: () => set({ replanFlash: false }),

  reset: () => set({ ...INITIAL }),
}));
