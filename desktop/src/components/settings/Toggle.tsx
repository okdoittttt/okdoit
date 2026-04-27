/** 34×20px iOS 스타일 pill 토글. */

import { TOKENS } from "@/styles/tokens";

interface Props {
  on: boolean;
  onChange: (next: boolean) => void;
  accent: string;
  disabled?: boolean;
}

export function Toggle({ on, onChange, accent, disabled = false }: Props) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!on)}
      disabled={disabled}
      aria-pressed={on}
      style={{
        position: "relative",
        width: 34,
        height: 20,
        background: on ? accent : TOKENS.borderStrong,
        border: 0,
        borderRadius: 999,
        cursor: disabled ? "not-allowed" : "pointer",
        padding: 0,
        opacity: disabled ? 0.5 : 1,
        transition: "background 0.15s",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: on ? 16 : 2,
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: "#fff",
          transition: "left 0.15s",
          boxShadow: "0 1px 2px rgba(0,0,0,0.4)",
        }}
      />
    </button>
  );
}
