/**
 * 세션 상태 store (멀티 세션).
 *
 * v0.3 부터 동시에 여러 세션을 다룬다. ``sessions`` 는 ``Record<sessionId, SessionData>``
 * 형태로 보관하고, ``activeSessionId`` 가 현재 화면에 보여지는 세션을 가리킨다.
 *
 * v0.5 부터 step 의 ``kind`` 가 design 시안과 1:1 로 정렬된다 — 4가지였던
 * ``thinking|acted|observed|verified`` 가 ``think|act|observe|verify`` 로 짧아졌고,
 * ``plan`` / ``success`` / ``error`` 가 추가되었다. ``plan`` 은 ``PlanCreated`` /
 * ``PlanReplanned`` 에서, ``success`` 는 ``SessionFinished`` 에서, ``error`` 는
 * ``SessionErrored`` 에서 만든다.
 *
 * 이벤트 적용 로직(``reduceEvent``)은 한 ``SessionData`` 단위에서 동작하는 순수
 * 함수로 분리해 단위 테스트가 쉽다. ``applyEvent`` 가 ``event.session_id`` 로 라우팅한다.
 */

import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";
import type { SessionSnapshot } from "@/lib/api";
import type {
  PlanCreated,
  PlanReplanned,
  ServerEvent,
  SessionErrored,
  SessionFinished,
  StepActed,
  StepObserved,
  StepThinking,
  StepVerified,
  Subtask,
} from "@/types/events";

// ── 도메인 타입 ────────────────────────────────────────────────

export type SessionStatus =
  | "idle"
  | "running"
  | "paused"
  | "finished"
  | "errored"
  | "stopped";

/** 활동 로그 카드의 종류. design/app.jsx 의 step.kind 와 동일. */
export type StepKind =
  | "plan"
  | "observe"
  | "think"
  | "act"
  | "verify"
  | "success"
  | "error";

export interface StepEntry {
  /** ``ts`` 와 함께 정렬 키로 쓰이는 단조 증가 ID. */
  id: number;
  /** 백엔드 iteration 번호. lifecycle 이벤트(plan/success/error)는 0. */
  iteration: number;
  kind: StepKind;
  /** 이벤트 ts(ISO). 카드 헤더의 경과 시간 표시에 사용. */
  ts: string;
  /** 카드 한 줄 요약(클립보드 복사 등에 사용). */
  summary: string;
  /** 원본 페이로드. 카드 본문이 narrowing 으로 다시 읽는다. */
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
  /** 정렬용 unix ms. 화면의 elapsed 표시에도 사용. */
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
  /**
   * sidecar ``GET /sessions`` 결과를 store 에 머지한다.
   *
   * 이미 메모리에 있는 세션(``sessions[id]`` 존재)은 건드리지 않는다 — 라이브
   * 진행 중인 데이터를 DB 스냅샷으로 덮어쓰면 step 카드가 사라진다. 신규
   * 항목만 ``status`` / ``task`` / ``startedAt`` (created_at 파싱) 으로 seed.
   *
   * step 은 비어있어 사용자가 클릭해 선택하면 wsManager.connect 가
   * ``?since_seq=0`` 으로 replay 해 채워준다.
   */
  mergeHistorical: (snapshots: SessionSnapshot[]) => void;
  reset: () => void;
}

// ── reducer (순수 함수) ────────────────────────────────────────

let nextStepId = 1;

/**
 * ``ServerEvent`` 를 받아 ``SessionData`` 변환분을 돌려준다(부수효과 없음).
 *
 * 이벤트가 추가되면 여기에 case 한 줄을 추가하면 된다 — exhaustive 검사가
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
        steps: [...data.steps, makeStep(event, "success", successSummary(event))],
      };

    case "session.errored":
      return {
        status: "errored",
        error: event.error,
        steps: [...data.steps, makeStep(event, "error", errorSummary(event))],
      };

    case "session.paused":
      return { status: "paused" };

    case "session.resumed":
      return { status: "running" };

    case "session.stopped":
      return { status: "stopped" };

    case "plan.created":
      return {
        subtasks: event.subtasks,
        activeSubtaskIndex: 0,
        steps: [...data.steps, makeStep(event, "plan", planSummary(event))],
      };

    case "plan.replanned":
      return {
        subtasks: event.subtasks,
        activeSubtaskIndex: 0,
        replanFlash: true,
        steps: [...data.steps, makeStep(event, "plan", replanSummary(event))],
      };

    case "subtask.activated":
      return { activeSubtaskIndex: event.index };

    case "step.thinking":
      return {
        steps: [...data.steps, makeStep(event, "think", thinkingSummary(event))],
        iterations: event.iteration,
      };

    case "step.acted":
      return {
        steps: [...data.steps, makeStep(event, "act", actedSummary(event))],
        iterations: event.iteration,
      };

    case "step.observed":
      return {
        steps: [...data.steps, makeStep(event, "observe", observedSummary(event))],
        iterations: event.iteration,
      };

    case "step.verified":
      return {
        steps: [...data.steps, makeStep(event, "verify", verifiedSummary(event))],
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
  // step.* 만 ``iteration`` 을 가진다. 라이프사이클 이벤트는 0 으로 둔다.
  const iteration =
    "iteration" in event && typeof event.iteration === "number"
      ? event.iteration
      : 0;
  return {
    id: nextStepId++,
    iteration,
    kind,
    ts: event.ts,
    summary,
    payload: event,
  };
}

function planSummary(e: PlanCreated): string {
  return `Plan with ${e.subtasks.length} subtask${e.subtasks.length === 1 ? "" : "s"}`;
}

function replanSummary(e: PlanReplanned): string {
  return `Replanned (${e.replan_count}): ${e.reason}`;
}

function successSummary(e: SessionFinished): string {
  return e.result ?? "(no result)";
}

function errorSummary(e: SessionErrored): string {
  return e.error;
}

function thinkingSummary(e: StepThinking): string {
  const actionName =
    typeof e.action.name === "string" ? e.action.name : "?";
  const thought = e.thought.length > 80 ? `${e.thought.slice(0, 80)}…` : e.thought;
  return `${thought}  →  ${actionName}`;
}

function actedSummary(e: StepActed): string {
  if (e.success) return `✓ ${e.action}`;
  return `✗ ${e.action} — ${e.error_message ?? "(unknown cause)"}`;
}

function observedSummary(e: StepObserved): string {
  const url = e.current_url || "(blank page)";
  return `${url}  ·  ${e.interactive_count} elements`;
}

function verifiedSummary(e: StepVerified): string {
  if (e.is_done) return "Done";
  if (e.consecutive_errors > 0) {
    return `Continuing (${e.consecutive_errors} consecutive errors)`;
  }
  return "Continuing";
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

/**
 * DB 스냅샷에서 SessionData 를 만든다.
 *
 * step / subtask 등 라이브 데이터는 비어있고, 사용자가 클릭해 선택하면 WS replay
 * 가 채운다. ``startedAt`` 은 ``created_at`` ISO 를 파싱한 ms — 사이드바의 상대
 * 시각/elapsed 표시에 사용. created_at 이 없거나 파싱 실패 시 fallback 으로
 * 현재 시각.
 */
function snapshotToSessionData(snap: SessionSnapshot): SessionData {
  const parsed =
    snap.created_at !== null ? Date.parse(snap.created_at) : Number.NaN;
  const startedAt = Number.isFinite(parsed) ? parsed : Date.now();
  return {
    id: snap.id,
    task: snap.task,
    status: snap.status,
    subtasks: [],
    activeSubtaskIndex: -1,
    steps: [],
    replanFlash: false,
    result: snap.result,
    error: snap.error,
    iterations: snap.iterations,
    startedAt,
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
      const nextActive =
        s.activeSessionId === sessionId ? null : s.activeSessionId;
      return { sessions: rest, activeSessionId: nextActive };
    }),

  mergeHistorical: (snapshots) =>
    set((s) => {
      const merged = { ...s.sessions };
      for (const snap of snapshots) {
        // 이미 메모리에 있는 세션은 라이브 데이터를 보존하기 위해 그대로 둔다.
        if (snap.id in merged) continue;
        merged[snap.id] = snapshotToSessionData(snap);
      }
      return { sessions: merged };
    }),

  reset: () => set({ sessions: {}, activeSessionId: null }),
}));

// ── selectors ────────────────────────────────────────────────

/**
 * 현재 화면에 보여지는 세션 데이터. 없으면 null.
 *
 * 단일 객체 참조 또는 ``null`` 만 돌려주므로 ``Object.is`` 비교만으로 충분 →
 * ``useShallow`` 불필요.
 */
export const useActiveSession = (): SessionData | null =>
  useSessions((s) =>
    s.activeSessionId ? (s.sessions[s.activeSessionId] ?? null) : null,
  );

/**
 * 세션 목록을 ``startedAt`` 내림차순으로 반환한다.
 *
 * ``Object.values().sort()`` 가 매 호출마다 새 배열을 만들기 때문에 그대로 두면
 * ``useSyncExternalStore`` 의 snapshot 안정성 규칙을 어겨 무한 re-render 가 발생한다.
 * ``useShallow`` 가 결과를 shallow 비교해 캐싱하므로 내용이 같으면 같은 참조를 돌려준다.
 */
export const useSessionList = (): SessionData[] =>
  useSessions(
    useShallow((s) =>
      Object.values(s.sessions).sort((a, b) => b.startedAt - a.startedAt),
    ),
  );
