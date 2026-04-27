/**
 * 가운데 패널의 활동 로그 영역.
 *
 * 헤더(``Activity`` 타이틀 + StatusBadge + 단계 수)와 스크롤되는 카드 리스트로
 * 구성. 새 카드가 추가될 때마다 맨 아래로 자동 스크롤한다.
 */

import { useEffect, useRef } from "react";
import { FONT_MONO, TOKENS, type StatusKey } from "@/styles/tokens";
import { StatusBadge } from "@/components/common/StatusBadge";
import type { StepEntry } from "@/stores/sessionStore";
import { StepCard } from "./StepCard";
import { EmptyState } from "./EmptyState";
import { ThinkingIndicator } from "./ThinkingIndicator";

interface Props {
  steps: StepEntry[];
  status: StatusKey;
  sessionStartedAt: number;
  density: "compact" | "regular" | "comfy";
  monoLogs: boolean;
  showThinking: boolean;
  accent: string;
}

export function ActivityLog({
  steps,
  status,
  sessionStartedAt,
  density,
  monoLogs,
  showThinking,
  accent,
}: Props) {
  const logRef = useRef<HTMLDivElement | null>(null);

  const filtered = showThinking ? steps : steps.filter((s) => s.kind !== "think");

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [filtered.length]);

  const isRunning = status === "running";

  return (
    <>
      <div
        style={{
          padding: "12px 20px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h2
            style={{
              margin: 0,
              fontSize: 13,
              fontWeight: 600,
              color: TOKENS.text,
              letterSpacing: 0.1,
            }}
          >
            Activity
          </h2>
          <StatusBadge status={status} />
        </div>
        <div
          style={{
            fontSize: 11,
            color: TOKENS.textFaint,
            fontFamily: FONT_MONO,
          }}
        >
          {filtered.length} step{filtered.length === 1 ? "" : "s"}
        </div>
      </div>

      <div
        ref={logRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "4px 20px 22px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {filtered.length === 0 && !isRunning && <EmptyState accent={accent} />}
        {filtered.map((entry) => (
          <StepCard
            key={entry.id}
            entry={entry}
            sessionStartedAt={sessionStartedAt}
            density={density}
            monoLogs={monoLogs}
          />
        ))}
        {isRunning && <ThinkingIndicator accent={accent} />}
      </div>
    </>
  );
}
