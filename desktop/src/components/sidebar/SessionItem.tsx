/**
 * 세션 목록의 항목.
 *
 * 활성/비활성, running glow 상태에 따라 배경/그림자가 달라진다. mouse hover 시
 * 비활성 항목은 ``surface`` 색으로 배경을 잠깐 띄운다.
 */

import type { CSSProperties, MouseEvent } from "react";
import { TOKENS, type StatusKey } from "@/styles/tokens";
import { StatusBadge } from "@/components/common/StatusBadge";

export interface SessionItemData {
  id: string;
  title: string;
  status: StatusKey;
  /** 경과 시간(초). */
  elapsed: number;
}

interface Props {
  session: SessionItemData;
  active: boolean;
  glow: boolean;
  accent: string;
  onClick: () => void;
}

/** ``s`` 초를 ``"42s"`` 또는 ``"3m 5s"`` 로 포맷. */
function fmtElapsed(s: number): string {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

export function SessionItem({ session, active, glow, accent, onClick }: Props) {
  const baseStyle: CSSProperties = {
    width: "100%",
    textAlign: "left",
    padding: "10px 12px",
    background: active ? `${accent}14` : "transparent",
    border: active ? `1px solid ${accent}55` : "1px solid transparent",
    borderRadius: 8,
    cursor: "pointer",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    position: "relative",
    boxShadow:
      active && glow && session.status === "running"
        ? `0 0 24px -6px ${accent}88, inset 0 0 0 1px ${accent}33`
        : "none",
    transition: "background 0.15s, border 0.15s, box-shadow 0.3s",
    fontFamily: "inherit",
  };

  function handleEnter(e: MouseEvent<HTMLButtonElement>): void {
    if (!active) e.currentTarget.style.background = TOKENS.surface;
  }
  function handleLeave(e: MouseEvent<HTMLButtonElement>): void {
    if (!active) e.currentTarget.style.background = "transparent";
  }

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      style={baseStyle}
    >
      <div
        style={{
          fontSize: 13,
          color: TOKENS.text,
          lineHeight: 1.35,
          fontWeight: active ? 500 : 450,
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {session.title}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <StatusBadge status={session.status} />
        <span
          style={{
            fontSize: 11,
            color: TOKENS.textFaint,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {fmtElapsed(session.elapsed)}
        </span>
      </div>
    </button>
  );
}
