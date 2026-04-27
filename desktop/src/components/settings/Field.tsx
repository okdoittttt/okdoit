/** 라벨 + 컨트롤 + 보조 설명을 묶은 필드 래퍼. */

import type { ReactNode } from "react";
import type { CSSProperties } from "react";
import { TOKENS } from "@/styles/tokens";

interface Props {
  label: string;
  hint?: string;
  children: ReactNode;
}

export function Field({ label, hint, children }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: TOKENS.textDim,
          letterSpacing: 0.2,
        }}
      >
        {label}
      </label>
      {children}
      {hint && (
        <span style={{ fontSize: 11, color: TOKENS.textFaint }}>{hint}</span>
      )}
    </div>
  );
}

/** ``input`` / ``select`` / ``textarea`` 의 공용 스타일. */
export const fieldStyle: CSSProperties = {
  width: "100%",
  height: 34,
  padding: "0 11px",
  background: TOKENS.surface2,
  border: `1px solid ${TOKENS.border}`,
  borderRadius: 7,
  color: TOKENS.text,
  fontSize: 12.5,
  fontFamily: "inherit",
  outline: "none",
  transition: "border 0.12s",
  boxSizing: "border-box",
};
