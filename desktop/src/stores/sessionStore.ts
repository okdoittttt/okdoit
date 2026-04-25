/**
 * 세션 상태 store (멀티 세션).
 *
 * v0.3 부터 동시에 여러 세션을 다룬다. ``sessions`` 는 ``Record<sessionId, SessionData>``
 * 형태로 보관하고, ``activeSessionId`` 가 현재 화면에 보여지는 세션을 가리킨다.
 *
 * 이벤트 적용 로직(``reduceEvent``)은 한 ``SessionData`` 단위에서 동작하는 순수
 * 함수로 분리해 단위 테스트가 쉽다. ``applyEvent`` 가 ``event.session_id`` 로 라우팅한다.
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

/**
 * 단일 세션의 화면 상태.
 *
 * 세션이 종료되어도 store 에 그대로 남아 사용자가 좌측에서 다시 열어볼 수 있다.
 */
export interface SessionData {
  id: string;
  task: string;
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
  /** 정렬용 unix ms. */
  startedAt: number;
}

export interface SessionsState {
  sessions: Record<string, SessionData>;
  activeSessionId: string | null;

  // ── 액션 ──
  startSession: (sessionId: string, task: string) => void;
  setActive: (sessionId: string | null) => void;
  applyEvent: (event: ServerEvent) => void;
  clearReplanFlash: (sessionId: string) => void;
  removeSession: (sessionId: string) => void;
  reset: () => void;
}

// ── reducer (순수 함수) ────────────────────────────────────────

let nextStepId = 1;

/**
 * ``ServerEvent`` 를 받아 ``SessionData`` 변환분을 돌려준다(부수효과 없음).
 *
 * 새 이벤트 타입이 생기면 여기에 case 한 줄을 추가하면 된다 — exhaustive 검사가
 * 누락을 컴파일 타임에 잡아준다.
 */
export function reduceEvent(
  data: SessionData,
  event: ServerEvent,
): Partial<SessionData> {
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
        steps: [...data.steps, makeStep(event, "thinking", thinkingSummary(event))],
        iterations: event.iteration,
      };

    case "step.acted":
      return {
        steps: [...data.steps, makeStep(event, "acted", actedSummary(event))],
        iterations: event.iteration,
      };

    case "step.observed":
      return {
        steps: [...data.steps, makeStep(event, "observed", observedSummary(event))],
        iterations: event.iteration,
      };

    case "step.verified":
      return {
        steps: [...data.steps, makeStep(event, "verified", verifiedSummary(event))],
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

// ── 새 SessionData 팩토리 ──────────────────────────────────────

function newSessionData(sessionId: string, task: string): SessionData {
  return {
    id: sessionId,
    task,
    status: "running",
    subtasks: [],
    activeSubtaskIndex: -1,
    steps: [],
    replanFlash: false,
    result: null,
    error: null,
    iterations: 0,
    startedAt: Date.now(),
  };
}

// ── 스토어 ────────────────────────────────────────────────────

export const useSessions = create<SessionsState>((set) => ({
  sessions: {},
  activeSessionId: null,

  startSession: (sessionId, task) =>
    set((s) => ({
      sessions: {
        ...s.sessions,
        [sessionId]: newSessionData(sessionId, task),
      },
      activeSessionId: sessionId,
    })),

  setActive: (sessionId) => set({ activeSessionId: sessionId }),

  applyEvent: (event) =>
    set((s) => {
      const sid = event.session_id;
      const current = s.sessions[sid];
      if (!current) return s;
      const update = reduceEvent(current, event);
      return {
        sessions: {
          ...s.sessions,
          [sid]: { ...current, ...update },
        },
      };
    }),

  clearReplanFlash: (sessionId) =>
    set((s) => {
      const current = s.sessions[sessionId];
      if (!current) return s;
      return {
        sessions: {
          ...s.sessions,
          [sessionId]: { ...current, replanFlash: false },
        },
      };
    }),

  removeSession: (sessionId) =>
    set((s) => {
      const { [sessionId]: _removed, ...rest } = s.sessions;
      const nextActive = s.activeSessionId === sessionId ? null : s.activeSessionId;
      return { sessions: rest, activeSessionId: nextActive };
    }),

  reset: () => set({ sessions: {}, activeSessionId: null }),
}));

// ── selectors ────────────────────────────────────────────────

/** 현재 화면에 보여지는 세션 데이터. 없으면 null. */
export const useActiveSession = (): SessionData | null =>
  useSessions((s) =>
    s.activeSessionId ? (s.sessions[s.activeSessionId] ?? null) : null,
  );

/** 세션 목록을 ``startedAt`` 내림차순으로 반환. */
export const useSessionList = (): SessionData[] =>
  useSessions((s) =>
    Object.values(s.sessions).sort((a, b) => b.startedAt - a.startedAt),
  );
