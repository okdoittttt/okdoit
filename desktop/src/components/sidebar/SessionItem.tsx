/**
 * 세션 목록의 항목.
 *
 * 활성/비활성, running glow 상태에 따라 배경/그림자가 달라진다. mouse hover 시
 * 비활성 항목은 ``surface`` 색으로 배경을 잠깐 띄운다. hover 시 우측에 휴지통
 * 아이콘이 보이고, 클릭하면 같은 자리에 "Delete? Yes / Cancel" 인라인 확인이
 * 뜬다.
 *
 * root 가 ``<div role="button">`` 인 이유: 인라인 confirm 의 Yes / Cancel 도
 * ``<button>`` 이라 native ``<button>`` 안에 넣으면 HTML 사양 위반이라.
 */

import { useState, type CSSProperties, type KeyboardEvent, type MouseEvent } from "react";
import { TOKENS, type StatusKey } from "@/styles/tokens";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Icon } from "@/components/common/Icon";

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
  /** 삭제 핸들러. 미지정이면 휴지통 아이콘이 노출되지 않는다. */
  onDelete?: (sessionId: string) => Promise<void>;
}

/** ``s`` 초를 ``"42s"`` 또는 ``"3m 5s"`` 로 포맷. */
function fmtElapsed(s: number): string {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

export function SessionItem({
  session,
  active,
  glow,
  accent,
  onClick,
  onDelete,
}: Props) {
  const [hover, setHover] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLive = session.status === "running" || session.status === "paused";

  const baseStyle: CSSProperties = {
    width: "100%",
    textAlign: "left",
    padding: "10px 12px",
    background: active
      ? `${accent}14`
      : hover && !confirming
        ? TOKENS.surface
        : "transparent",
    border: active ? `1px solid ${accent}55` : "1px solid transparent",
    borderRadius: 8,
    cursor: confirming || deleting ? "default" : "pointer",
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
    opacity: deleting ? 0.55 : 1,
  };

  function handleRootClick(): void {
    if (confirming || deleting) return;
    onClick();
  }

  function handleRootKeyDown(e: KeyboardEvent<HTMLDivElement>): void {
    if (confirming || deleting) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  }

  function handleTrashClick(e: MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation();
    if (!onDelete || deleting) return;
    setError(null);
    setConfirming(true);
  }

  function handleCancel(e: MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation();
    if (deleting) return;
    setConfirming(false);
    setError(null);
  }

  async function handleConfirm(e: MouseEvent<HTMLButtonElement>): Promise<void> {
    e.stopPropagation();
    if (!onDelete || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await onDelete(session.id);
      // 성공 시 부모가 store 에서 제거 → 이 컴포넌트는 unmount. state reset 불필요.
    } catch (err) {
      console.error("[SessionItem] delete 실패:", err);
      setError("삭제 실패");
      setDeleting(false);
    }
  }

  return (
    <div
      role="button"
      tabIndex={confirming || deleting ? -1 : 0}
      aria-pressed={active}
      aria-busy={deleting}
      onClick={handleRootClick}
      onKeyDown={handleRootKeyDown}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={baseStyle}
    >
      {confirming ? (
        <ConfirmRow
          isLive={isLive}
          deleting={deleting}
          error={error}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          accent={accent}
        />
      ) : (
        <NormalRow
          session={session}
          active={active}
          showTrash={hover && !!onDelete}
          onTrashClick={handleTrashClick}
        />
      )}
    </div>
  );
}

// ── 내부 서브뷰 ────────────────────────────────────────────────

interface NormalRowProps {
  session: SessionItemData;
  active: boolean;
  showTrash: boolean;
  onTrashClick: (e: MouseEvent<HTMLButtonElement>) => void;
}

function NormalRow({ session, active, showTrash, onTrashClick }: NormalRowProps) {
  return (
    <>
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
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontSize: 11,
              color: TOKENS.textFaint,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {fmtElapsed(session.elapsed)}
          </span>
          {showTrash && (
            <button
              type="button"
              onClick={onTrashClick}
              aria-label="세션 삭제"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 22,
                height: 22,
                borderRadius: 4,
                border: "none",
                background: "transparent",
                color: TOKENS.textFaint,
                cursor: "pointer",
                padding: 0,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = TOKENS.surface;
                e.currentTarget.style.color = TOKENS.text;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = TOKENS.textFaint;
              }}
            >
              <Icon name="trash" size={13} />
            </button>
          )}
        </div>
      </div>
    </>
  );
}

interface ConfirmRowProps {
  isLive: boolean;
  deleting: boolean;
  error: string | null;
  onConfirm: (e: MouseEvent<HTMLButtonElement>) => void;
  onCancel: (e: MouseEvent<HTMLButtonElement>) => void;
  accent: string;
}

function ConfirmRow({
  isLive,
  deleting,
  error,
  onConfirm,
  onCancel,
  accent,
}: ConfirmRowProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        // 평소 두 줄 + 하단 메타와 비슷한 높이를 유지해 사이드바가 점프 안 하게.
        minHeight: 48,
        justifyContent: "center",
      }}
    >
      <div
        style={{
          fontSize: 12,
          color: TOKENS.text,
          lineHeight: 1.4,
        }}
      >
        {isLive
          ? "실행 중인 세션을 안전 종료 후 삭제할까요?"
          : "이 세션을 삭제할까요?"}
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <button
          type="button"
          onClick={onConfirm}
          disabled={deleting}
          style={{
            fontSize: 11,
            padding: "4px 10px",
            borderRadius: 4,
            border: `1px solid ${accent}66`,
            background: `${accent}22`,
            color: TOKENS.text,
            cursor: deleting ? "wait" : "pointer",
            fontFamily: "inherit",
          }}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={deleting}
          style={{
            fontSize: 11,
            padding: "4px 10px",
            borderRadius: 4,
            border: `1px solid ${TOKENS.border}`,
            background: "transparent",
            color: TOKENS.textFaint,
            cursor: deleting ? "wait" : "pointer",
            fontFamily: "inherit",
          }}
        >
          Cancel
        </button>
        {error && (
          <span style={{ fontSize: 11, color: "#e57373" }}>{error}</span>
        )}
      </div>
    </div>
  );
}
