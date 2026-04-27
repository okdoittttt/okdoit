/** 에이전트가 작업 중일 때 표시하는 점 3개 깜박이 인디케이터. */

import { FONT_MONO, TOKENS } from "@/styles/tokens";

interface Props {
  accent: string;
}

export function ThinkingIndicator({ accent }: Props) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 14px",
        fontFamily: FONT_MONO,
        fontSize: 12,
        color: TOKENS.textDim,
      }}
    >
      <div style={{ display: "flex", gap: 4 }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: accent,
              animation: `blink 1.2s ${i * 0.18}s ease-in-out infinite`,
            }}
          />
        ))}
      </div>
      <span>agent working…</span>
    </div>
  );
}
