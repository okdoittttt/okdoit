/**
 * 상태 배지(running / done / failed / paused / idle).
 *
 * design/app.jsx 의 ``StatusBadge`` 와 동일한 비주얼. ``running`` 일 때만 점이
 * 펄스 애니메이션을 돈다.
 */

import { FONT_SANS, STATUS_META, type StatusKey } from "@/styles/tokens";

interface Props {
  status: StatusKey;
  size?: "sm" | "lg";
}

export function StatusBadge({ status, size = "sm" }: Props) {
  const meta = STATUS_META[status] ?? STATUS_META.idle;
  const px =
    size === "lg"
      ? { h: 22, fs: 11, px: 9 }
      : { h: 18, fs: 10, px: 7 };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        height: px.h,
        padding: `0 ${px.px}px`,
        fontSize: px.fs,
        fontWeight: 600,
        letterSpacing: 0.3,
        borderRadius: 999,
        color: meta.color,
        background: `${meta.color}1A`,
        border: `1px solid ${meta.color}33`,
        fontFamily: FONT_SANS,
      }}
    >
      {meta.dot && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: meta.color,
            boxShadow: `0 0 0 0 ${meta.color}`,
            animation: "pulse 1.6s ease-out infinite",
          }}
        />
      )}
      {meta.label}
    </span>
  );
}
