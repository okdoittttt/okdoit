/**
 * 편집 모드 설정 모달.
 *
 * Esc / 바깥 클릭 / 헤더 X 버튼으로 닫을 수 있다. 첫 실행에서는 사용하지 않는다
 * (그쪽은 ``SettingsView`` 풀스크린).
 */

import { useEffect } from "react";
import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import { iconBtn } from "@/components/common/buttonStyles";
import { SettingsForm } from "./SettingsForm";

interface Props {
  onClose: () => void;
}

export function SettingsModal({ onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 50,
        background: "rgba(0,0,0,0.55)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 40,
        animation: "fadeIn 0.18s ease-out",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 460,
          maxHeight: "calc(100vh - 80px)",
          overflowY: "auto",
          background: TOKENS.surface,
          border: `1px solid ${TOKENS.borderStrong}`,
          borderRadius: 12,
          boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
          animation: "modalIn 0.22s cubic-bezier(.2,.7,.3,1)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: `1px solid ${TOKENS.border}`,
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 14,
              fontWeight: 600,
              color: TOKENS.text,
            }}
          >
            Settings
          </h2>
          <button
            type="button"
            onClick={onClose}
            title="Close"
            style={{
              ...iconBtn(false),
              width: 26,
              height: 26,
              padding: 0,
              justifyContent: "center",
            }}
          >
            <Icon name="x" size={12} />
          </button>
        </div>
        <div style={{ padding: 20 }}>
          <SettingsForm variant="edit" onClose={onClose} />
        </div>
      </div>
    </div>
  );
}
