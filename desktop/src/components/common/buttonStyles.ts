/**
 * 디자인 시안의 버튼 스타일 팩토리.
 *
 * 스타일을 인라인으로 적용해야 하므로 ``CSSProperties`` 객체를 돌려주는 팩토리
 * 형태로 보관한다(design/app.jsx 의 ``primaryBtn`` / ``ghostBtn`` / ``dangerBtn`` /
 * ``iconBtn`` 와 일치).
 */

import type { CSSProperties } from "react";
import { TOKENS } from "@/styles/tokens";

export function primaryBtn(accent: string = TOKENS.accent): CSSProperties {
  return {
    height: 30,
    padding: "0 14px",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    background: accent,
    color: "#fff",
    border: 0,
    borderRadius: 7,
    fontSize: 12.5,
    fontWeight: 600,
    fontFamily: "inherit",
    cursor: "pointer",
    boxShadow: `0 0 0 1px ${accent}, 0 6px 16px -4px ${accent}88`,
  };
}

export function ghostBtn(): CSSProperties {
  return {
    height: 30,
    padding: "0 12px",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    background: TOKENS.surface2,
    color: TOKENS.text,
    border: `1px solid ${TOKENS.border}`,
    borderRadius: 7,
    fontSize: 12.5,
    fontWeight: 500,
    fontFamily: "inherit",
    cursor: "pointer",
  };
}

export function dangerBtn(): CSSProperties {
  return {
    height: 30,
    padding: "0 12px",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    background: "transparent",
    color: TOKENS.error,
    border: `1px solid ${TOKENS.error}55`,
    borderRadius: 7,
    fontSize: 12.5,
    fontWeight: 500,
    fontFamily: "inherit",
    cursor: "pointer",
  };
}

export function iconBtn(active: boolean): CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    height: 22,
    padding: "0 7px",
    background: active ? TOKENS.surface2 : "transparent",
    border: `1px solid ${active ? TOKENS.borderStrong : TOKENS.border}`,
    borderRadius: 5,
    color: TOKENS.textDim,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 11,
    transition: "background 0.1s, border 0.1s",
  };
}

/** 키보드 단축키 표기용 ``<kbd>`` 스타일. */
export const kbdStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: 16,
  height: 16,
  padding: "0 4px",
  fontSize: 10,
  fontFamily: "inherit",
  color: TOKENS.textDim,
  background: "#0A0A0A",
  border: `1px solid ${TOKENS.border}`,
  borderRadius: 4,
};
