/**
 * StepCard 의 본문. ``entry.kind`` 별로 다른 비주얼을 그린다.
 *
 * 각 변형은 design/app.jsx 의 ``StepBody`` 와 1:1 대응:
 *   - plan: 번호 매김된 서브태스크 리스트(✓/▶/· 진행 상태 포함)
 *   - observe: globe 아이콘 + URL + 요소 개수
 *   - think: italic, 흐릿한 텍스트
 *   - act: 모노스페이스 시그니처 + 성공/실패 색상
 *   - verify: ``iter / max`` 진행바 + 메모
 *   - success: 결과 텍스트
 *   - error: 빨간색 에러 메시지
 */

import { FONT_MONO, FONT_SANS, TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import type { StepEntry } from "@/stores/sessionStore";
import type {
  PlanCreated,
  PlanReplanned,
  SessionErrored,
  SessionFinished,
  StepActed,
  StepObserved,
  StepThinking,
  StepVerified,
  Subtask,
} from "@/types/events";

interface Props {
  entry: StepEntry;
  monoLogs: boolean;
}

const TXT_SIZE = 12.5;

/** ``MAX_ITER`` 는 backend 의 ``MAX_LOOP_ITERATIONS`` 와 같은 값(상한). */
const MAX_ITER = 20;

export function StepBody({ entry, monoLogs }: Props) {
  const monoFont = monoLogs ? FONT_MONO : FONT_SANS;

  if (entry.kind === "plan") {
    const ev = entry.payload as PlanCreated | PlanReplanned;
    const replanned = ev.type === "plan.replanned";
    const reason = replanned ? (ev as PlanReplanned).reason : null;
    return <PlanBody subtasks={ev.subtasks} replanned={replanned} reason={reason} mono={monoFont} />;
  }

  if (entry.kind === "observe") {
    const ev = entry.payload as StepObserved;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontFamily: monoFont,
            fontSize: 11.5,
            color: TOKENS.textDim,
          }}
        >
          <Icon name="globe" size={11} color={TOKENS.textFaint} />
          <span style={{ color: TOKENS.cyan, wordBreak: "break-all" }}>
            {ev.current_url || "about:blank"}
          </span>
        </div>
        <div style={{ fontSize: TXT_SIZE, lineHeight: 1.5, color: TOKENS.text }}>
          Detected {ev.interactive_count} interactive element
          {ev.interactive_count === 1 ? "" : "s"}.
        </div>
      </div>
    );
  }

  if (entry.kind === "think") {
    const ev = entry.payload as StepThinking;
    return (
      <div
        style={{
          fontSize: TXT_SIZE,
          lineHeight: 1.55,
          color: TOKENS.textDim,
          fontStyle: "italic",
        }}
      >
        {ev.thought}
      </div>
    );
  }

  if (entry.kind === "act") {
    const ev = entry.payload as StepActed;
    return <ActBody event={ev} mono={monoFont} />;
  }

  if (entry.kind === "verify") {
    const ev = entry.payload as StepVerified;
    const pct = Math.min(100, (ev.iteration / MAX_ITER) * 100);
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            fontFamily: monoFont,
            fontSize: 12,
          }}
        >
          <span style={{ color: TOKENS.text, fontWeight: 600 }}>
            iter {ev.iteration} / {MAX_ITER}
          </span>
          <div
            style={{
              flex: 1,
              height: 4,
              background: TOKENS.surface2,
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${pct}%`,
                height: "100%",
                background: TOKENS.warn,
                transition: "width 0.4s",
              }}
            />
          </div>
        </div>
        <div
          style={{
            fontSize: TXT_SIZE,
            color: TOKENS.textDim,
            lineHeight: 1.5,
          }}
        >
          {ev.is_done
            ? "Required data extracted. Wrapping up."
            : ev.consecutive_errors > 0
              ? `Continuing — ${ev.consecutive_errors} consecutive error${ev.consecutive_errors === 1 ? "" : "s"}.`
              : "Continuing."}
        </div>
      </div>
    );
  }

  if (entry.kind === "success") {
    const ev = entry.payload as SessionFinished;
    return (
      <div
        style={{
          fontSize: TXT_SIZE,
          color: TOKENS.text,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
        }}
      >
        {ev.result ?? "(no result)"}
      </div>
    );
  }

  if (entry.kind === "error") {
    const ev = entry.payload as SessionErrored;
    return (
      <div
        style={{
          fontSize: TXT_SIZE,
          color: TOKENS.error,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
        }}
      >
        {ev.error}
      </div>
    );
  }

  return null;
}

// ── 변형: plan ──────────────────────────────────────────────────

interface PlanBodyProps {
  subtasks: Subtask[];
  replanned: boolean;
  reason: string | null;
  mono: string;
}

function PlanBody({ subtasks, replanned, reason, mono }: PlanBodyProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {replanned && reason && (
        <div
          style={{
            fontSize: 11.5,
            color: TOKENS.warn,
            fontFamily: mono,
            lineHeight: 1.5,
          }}
        >
          Replanned: {reason}
        </div>
      )}
      <ol
        style={{
          margin: 0,
          paddingLeft: 0,
          listStyle: "none",
          fontFamily: mono,
          fontSize: TXT_SIZE,
          color: TOKENS.text,
          lineHeight: 1.7,
        }}
      >
        {subtasks.map((s, i) => (
          <li
            key={s.index}
            style={{ display: "flex", gap: 10, paddingLeft: 4 }}
          >
            <span
              style={{
                color: TOKENS.textFaint,
                width: 18,
                flexShrink: 0,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            <span
              style={{
                color: s.done ? TOKENS.textFaint : TOKENS.text,
                textDecoration: s.done ? "line-through" : "none",
                flex: 1,
              }}
            >
              {s.description}
            </span>
            <span
              style={{
                color: s.done
                  ? TOKENS.success
                  : TOKENS.textFaint,
                width: 12,
                flexShrink: 0,
                textAlign: "right",
              }}
            >
              {s.done ? "✓" : "·"}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ── 변형: act ───────────────────────────────────────────────────

interface ActBodyProps {
  event: StepActed;
  mono: string;
}

/** ``click(button.submit)`` 같은 시그니처를 ``verb`` + ``args`` 로 분해. */
function splitActSignature(sig: string): { verb: string; args: string } {
  const m = sig.match(/^([A-Za-z_][\w]*)\((.*)\)$/s);
  if (!m) return { verb: sig, args: "" };
  return { verb: m[1] ?? sig, args: m[2] ?? "" };
}

function ActBody({ event, mono }: ActBodyProps) {
  const { verb, args } = splitActSignature(event.action);
  const verbColor = event.success ? TOKENS.accent : TOKENS.error;
  return (
    <div
      style={{
        fontFamily: mono,
        fontSize: 12,
        lineHeight: 1.6,
        wordBreak: "break-all",
      }}
    >
      <span style={{ color: verbColor, fontWeight: 600 }}>{verb}</span>
      <span style={{ color: TOKENS.textFaint }}>(</span>
      <span style={{ color: TOKENS.text }}>{args}</span>
      <span style={{ color: TOKENS.textFaint }}>)</span>
      {!event.success && event.error_message && (
        <div
          style={{
            marginTop: 6,
            color: TOKENS.error,
            fontSize: 11.5,
            fontFamily: FONT_SANS,
            fontStyle: "italic",
          }}
        >
          {event.error_message}
        </div>
      )}
    </div>
  );
}
