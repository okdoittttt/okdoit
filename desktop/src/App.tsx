import { useEffect, useState } from "react";

/**
 * v0.1 placeholder UI.
 *
 * sidecar 와의 연결만 검증한다. 본격 UI(3-pane 레이아웃, 활동 로그, 입력창 등)는
 * 04 단계(`.plan/04-frontend-ui.md`)에서 구현한다.
 */

type HealthState =
  | { status: "loading" }
  | { status: "ok"; protocolVersion: string }
  | { status: "error"; message: string };

export default function App() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    const url = `${window.okdoit.sidecarUrl}/health`;
    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(`status ${res.status}`);
        const body = (await res.json()) as { protocol_version: string };
        setHealth({ status: "ok", protocolVersion: body.protocol_version });
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);
        setHealth({ status: "error", message });
      });
  }, []);

  return (
    <main
      style={{
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: "32px",
        color: "#111",
      }}
    >
      <h1 style={{ fontSize: "24px", marginBottom: "8px" }}>okdoit</h1>
      <p style={{ color: "#666", marginBottom: "24px" }}>
        v0.1 — sidecar 연결 확인용 placeholder. UI 본체는 04 단계에서.
      </p>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: "8px",
          padding: "16px",
          maxWidth: "480px",
          background: "#fafafa",
        }}
      >
        <h2 style={{ fontSize: "14px", margin: 0, color: "#888" }}>
          Sidecar Health
        </h2>
        <div style={{ marginTop: "8px" }}>
          {health.status === "loading" && <code>확인 중…</code>}
          {health.status === "ok" && (
            <code style={{ color: "#0a7d28" }}>
              ✅ ok · protocol {health.protocolVersion}
            </code>
          )}
          {health.status === "error" && (
            <code style={{ color: "#b00020" }}>
              ❌ {health.message}
            </code>
          )}
        </div>
        <div style={{ marginTop: "16px", fontSize: "12px", color: "#888" }}>
          <div>Sidecar URL: <code>{window.okdoit.sidecarUrl}</code></div>
          <div>WebSocket URL: <code>{window.okdoit.wsUrl}</code></div>
          <div>Platform: <code>{window.okdoit.platform}</code></div>
        </div>
      </section>
    </main>
  );
}
