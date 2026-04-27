/**
 * 첫 실행 풀스크린 설정 화면.
 *
 * 사용자가 설정을 저장하기 전에는 sidecar 가 부팅되지 않으므로 닫기 버튼이
 * 없다(``SettingsForm`` 의 ``variant="first-run"`` 모드 사용). 저장 후 main 이
 * webContents.reload() 를 호출하면 자연스럽게 화면이 다시 그려진다.
 */

import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import { SettingsForm } from "./SettingsForm";

export function SettingsView() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "radial-gradient(ellipse at top, #1a1a1a 0%, #050505 60%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 40,
        overflow: "auto",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 520,
          background: TOKENS.surface,
          border: `1px solid ${TOKENS.borderStrong}`,
          borderRadius: 12,
          boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
          padding: 28,
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 8,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: `${TOKENS.accent}14`,
              border: `1px solid ${TOKENS.accent}33`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name="spark" size={18} color={TOKENS.accent} />
          </div>
          <div>
            <h1
              style={{
                margin: 0,
                fontSize: 16,
                fontWeight: 600,
                color: TOKENS.text,
              }}
            >
              Welcome to okdoit
            </h1>
            <p
              style={{
                margin: "4px 0 0",
                fontSize: 12.5,
                color: TOKENS.textDim,
                lineHeight: 1.5,
              }}
            >
              Pick your LLM provider and paste an API key to get started.
            </p>
          </div>
        </header>
        <div style={{ marginTop: 22 }}>
          <SettingsForm variant="first-run" />
        </div>
      </div>
    </div>
  );
}
