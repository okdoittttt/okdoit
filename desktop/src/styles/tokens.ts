/**
 * 디자인 토큰.
 *
 * design/app.jsx 의 ``TOKENS`` / ``STEP_META`` / ``STATUS_META`` 와 1:1 동기화.
 * 인라인 ``style`` 으로 소비하므로 모든 값은 문자열 리터럴.
 */

export const TOKENS = {
  bg: "#0D0D0D",
  surface: "#161616",
  surface2: "#1C1C1C",
  border: "#262626",
  borderStrong: "#333333",
  text: "#EDEDED",
  textDim: "#9A9A9A",
  textFaint: "#6B6B6B",
  accent: "#3B82F6",
  success: "#22C55E",
  error: "#EF4444",
  warn: "#F59E0B",
  purple: "#A78BFA",
  cyan: "#22D3EE",
} as const;

export const FONT_SANS =
  'Inter, -apple-system, BlinkMacSystemFont, system-ui, "Apple SD Gothic Neo", "Pretendard", sans-serif';
export const FONT_MONO =
  '"JetBrains Mono", "SF Mono", ui-monospace, Menlo, monospace';

/** 활동 로그의 step 종류. design/app.jsx 의 ``step.kind`` 와 동일. */
export type StepKind =
  | "plan"
  | "observe"
  | "think"
  | "act"
  | "verify"
  | "success"
  | "error";

export interface StepMeta {
  label: string;
  color: string;
  glyph: string;
}

export const STEP_META: Record<StepKind, StepMeta> = {
  plan: { label: "PLAN", color: TOKENS.purple, glyph: "□" },
  observe: { label: "OBSERVE", color: TOKENS.cyan, glyph: "○" },
  think: { label: "THINK", color: TOKENS.textDim, glyph: "→" },
  act: { label: "ACT", color: TOKENS.accent, glyph: "▸" },
  verify: { label: "VERIFY", color: TOKENS.warn, glyph: "◆" },
  success: { label: "SUCCESS", color: TOKENS.success, glyph: "✓" },
  error: { label: "ERROR", color: TOKENS.error, glyph: "×" },
};

/** 세션 카드/뱃지에 쓰는 상태. backend 의 ``SessionStatus`` 와 매핑된다. */
export type StatusKey = "running" | "done" | "failed" | "paused" | "idle";

export interface StatusMeta {
  label: string;
  color: string;
  /** 펄스 점을 표시할지(running 만 true). */
  dot: boolean;
}

export const STATUS_META: Record<StatusKey, StatusMeta> = {
  running: { label: "Running", color: TOKENS.accent, dot: true },
  done: { label: "Done", color: TOKENS.success, dot: false },
  failed: { label: "Failed", color: TOKENS.error, dot: false },
  paused: { label: "Paused", color: TOKENS.warn, dot: false },
  idle: { label: "Idle", color: TOKENS.textFaint, dot: false },
};
