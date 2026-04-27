/**
 * 활동 로그의 한 줄 카드.
 *
 * 좌측 컬러 레일 + 헤더(LABEL · 경과초 · 펼침/복사 버튼) + StepBody.
 * stepIn 키프레임으로 부드럽게 등장한다.
 */

import { useState, type CSSProperties } from "react";
import { FONT_MONO, STEP_META, TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import { iconBtn } from "@/components/common/buttonStyles";
import type { StepEntry } from "@/stores/sessionStore";
import { StepBody } from "./StepBody";

interface Props {
  entry: StepEntry;
  /** 세션 시작 시각(ms). 헤더의 ``"0007s"`` 표기는 여기 기준 경과 시간. */
  sessionStartedAt: number;
  density: "compact" | "regular" | "comfy";
  monoLogs: boolean;
}

/** 4자리 zero-pad + ``s``. ``7.34`` → ``"0007"``. */
function fmtElapsedSec(ms: number): string {
  const sec = Math.max(0, Math.floor(ms / 1000));
  return String(sec).padStart(4, "0");
}

export function StepCard({
  entry,
  sessionStartedAt,
  density,
  monoLogs,
}: Props) {
  const meta = STEP_META[entry.kind];
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const pad = density === "compact" ? 10 : density === "comfy" ? 16 : 13;
  const elapsedMs = Date.parse(entry.ts) - sessionStartedAt;

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(entry.summary);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* noop — clipboard API 실패는 시각 피드백만 생략. */
    }
  }

  const cardStyle: CSSProperties = {
    animation: "stepIn 0.32s cubic-bezier(.2,.7,.3,1)",
    background: TOKENS.surface,
    border: `1px solid ${TOKENS.border}`,
    borderRadius: 8,
    padding: pad,
    position: "relative",
  };

  const headerMargin =
    entry.kind === "think" && !expanded ? 0 : 8;

  return (
    <div style={cardStyle}>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 10,
          bottom: 10,
          width: 2,
          background: meta.color,
          opacity: 0.7,
          borderRadius: 2,
        }}
      />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: headerMargin,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: 0.8,
            color: meta.color,
            fontFamily: FONT_MONO,
          }}
        >
          {meta.label}
        </span>
        <span
          style={{
            fontSize: 11,
            color: TOKENS.textFaint,
            fontFamily: FONT_MONO,
          }}
        >
          {fmtElapsedSec(elapsedMs)}
          <span style={{ opacity: 0.5 }}>s</span>
        </span>
        <div style={{ flex: 1 }} />
        {entry.kind === "think" && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            style={iconBtn(expanded)}
          >
            <span
              style={{
                transform: expanded ? "rotate(0deg)" : "rotate(-90deg)",
                transition: "transform 0.15s",
                display: "inline-flex",
              }}
            >
              <Icon name="chev" size={12} />
            </span>
          </button>
        )}
        {entry.kind === "success" && (
          <button
            type="button"
            onClick={() => void handleCopy()}
            style={iconBtn(copied)}
          >
            <Icon name={copied ? "check" : "copy"} size={12} />
            <span style={{ marginLeft: 4, fontSize: 11 }}>
              {copied ? "Copied" : "Copy"}
            </span>
          </button>
        )}
      </div>
      {expanded && <StepBody entry={entry} monoLogs={monoLogs} />}
    </div>
  );
}
