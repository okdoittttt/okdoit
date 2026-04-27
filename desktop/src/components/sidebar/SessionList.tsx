/**
 * 좌측 232px 고정 사이드바.
 *
 * 상단 ``+ New task`` 버튼, 가운데 세션 목록, 하단 모델/버전 표기.
 * design/app.jsx 의 ``SessionList`` 와 동일한 레이아웃.
 */

import type { MouseEvent } from "react";
import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import { kbdStyle } from "@/components/common/buttonStyles";
import { SessionItem, type SessionItemData } from "./SessionItem";

interface Props {
  sessions: SessionItemData[];
  activeId: string | null;
  accent: string;
  glow: boolean;
  modelLabel: string;
  versionLabel: string;
  onSelect: (id: string | null) => void;
  onNew: () => void;
}

export function SessionList({
  sessions,
  activeId,
  accent,
  glow,
  modelLabel,
  versionLabel,
  onSelect,
  onNew,
}: Props) {
  function handleNewEnter(e: MouseEvent<HTMLButtonElement>): void {
    e.currentTarget.style.background = TOKENS.surface2;
    e.currentTarget.style.borderColor = TOKENS.borderStrong;
  }
  function handleNewLeave(e: MouseEvent<HTMLButtonElement>): void {
    e.currentTarget.style.background = TOKENS.surface;
    e.currentTarget.style.borderColor = TOKENS.border;
  }

  return (
    <aside
      style={{
        width: 232,
        flexShrink: 0,
        background: "#0A0A0A",
        borderRight: `1px solid ${TOKENS.border}`,
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
      }}
    >
      <div
        style={{
          padding: 12,
          borderBottom: `1px solid ${TOKENS.border}`,
        }}
      >
        <button
          type="button"
          onClick={onNew}
          onMouseEnter={handleNewEnter}
          onMouseLeave={handleNewLeave}
          style={{
            width: "100%",
            height: 34,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            background: TOKENS.surface,
            border: `1px solid ${TOKENS.border}`,
            borderRadius: 7,
            color: TOKENS.text,
            fontSize: 12.5,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "background 0.12s, border 0.12s",
          }}
        >
          <Icon name="plus" size={13} />
          <span>New task</span>
          <span style={{ marginLeft: "auto", display: "flex", gap: 3 }}>
            <kbd style={kbdStyle}>⌘</kbd>
            <kbd style={kbdStyle}>N</kbd>
          </span>
        </button>
      </div>
      <div
        style={{
          padding: "8px 10px 4px",
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: 0.8,
          color: TOKENS.textFaint,
          textTransform: "uppercase",
        }}
      >
        Sessions
      </div>
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "0 8px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        {sessions.length === 0 ? (
          <div
            style={{
              padding: "20px 8px",
              fontSize: 11.5,
              color: TOKENS.textFaint,
              lineHeight: 1.5,
            }}
          >
            No sessions yet. Hit{" "}
            <kbd style={kbdStyle}>⌘</kbd> <kbd style={kbdStyle}>N</kbd> to start.
          </div>
        ) : (
          sessions.map((s) => (
            <SessionItem
              key={s.id}
              session={s}
              active={s.id === activeId}
              glow={glow}
              accent={accent}
              onClick={() => onSelect(s.id)}
            />
          ))
        )}
      </div>
      <div
        style={{
          padding: "10px 14px",
          borderTop: `1px solid ${TOKENS.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 11,
          color: TOKENS.textFaint,
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: TOKENS.success,
            }}
          />
          {modelLabel}
        </span>
        <span style={{ fontVariantNumeric: "tabular-nums" }}>
          {versionLabel}
        </span>
      </div>
    </aside>
  );
}
