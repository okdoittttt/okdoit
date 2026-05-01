/**
 * 앱 루트.
 *
 * 흐름:
 *   1) 부팅 시 ``window.okdoit.settings.status()`` 로 ready 여부 확인.
 *   2) ready=false → 풀스크린 ``SettingsView``. 저장 후 main 이 reload 트리거.
 *   3) ready=true  → ``WindowFrame`` 안에 좌(SessionList) / 중(CenterPane) /
 *      우(ResultPane) 3-패널 레이아웃. 우상단 ⚙ 버튼이 ``SettingsModal`` 을 띄운다.
 *
 * WS 연결은 ``wsManager`` 가 일괄 관리. ``startSession`` 시점에 connect 되고,
 * backend 가 ``close_stream`` 하면 자동 disconnect.
 */

import { useEffect, useMemo, useState } from "react";
import { TOKENS, type StatusKey } from "@/styles/tokens";
import { WindowFrame } from "@/components/chrome/WindowFrame";
import { SessionList } from "@/components/sidebar/SessionList";
import type { SessionItemData } from "@/components/sidebar/SessionItem";
import { CenterPane } from "@/components/center/CenterPane";
import { ResultPane } from "@/components/result/ResultPane";
import { SettingsView } from "@/components/settings/SettingsView";
import { SettingsModal } from "@/components/settings/SettingsModal";
import { getSessions } from "@/lib/api";
import {
  useActiveSession,
  useSessionList,
  useSessions,
  type SessionData,
} from "@/stores/sessionStore";
import { wsManager } from "@/ws/wsManager";

type ReadyState = "loading" | "first-run" | "ready";

const ACCENT = TOKENS.accent;


export default function App() {
  const [readyState, setReadyState] = useState<ReadyState>("loading");
  const [showSettings, setShowSettings] = useState(false);
  const [task, setTask] = useState<string>("");
  const [resultCollapsed, setResultCollapsed] = useState(false);

  const activeSession = useActiveSession();
  const sessionList = useSessionList();
  const setActive = useSessions((s) => s.setActive);
  const mergeHistorical = useSessions((s) => s.mergeHistorical);

  useEffect(() => {
    void window.okdoit.settings.status().then(({ ready }) => {
      setReadyState(ready ? "ready" : "first-run");
    });
  }, []);

  useEffect(() => {
    return () => wsManager.disconnectAll();
  }, []);

  // 부팅 후 ready 가 되면 sidecar 의 세션 목록을 한 번 가져와 사이드바에 머지.
  // 라이브 진행 중인 세션은 ``mergeHistorical`` 이 자동으로 건드리지 않는다.
  useEffect(() => {
    if (readyState !== "ready") return;
    let cancelled = false;
    getSessions()
      .then((snaps) => {
        if (!cancelled) mergeHistorical(snaps);
      })
      .catch((err: unknown) => {
        console.warn("[app] GET /sessions 실패:", err);
      });
    return () => {
      cancelled = true;
    };
  }, [readyState, mergeHistorical]);

  // 활성/비활성 무관 — 사용자가 선택한 세션의 step 카드가 비어있으면 WS 에 연결해
  // ``?since_seq=0`` 으로 누락분(과거 세션은 전체) replay 받는다. wsManager.connect
  // 는 idempotent 라 TaskInputBox 가 이미 연 연결을 중복 열지 않는다. 비활성 세션은
  // sidecar 가 replay 후 close 하고, 활성 세션은 그대로 라이브 큐로 진입한다.
  useEffect(() => {
    if (!activeSession) return;
    if (activeSession.steps.length > 0) return;
    wsManager.connect(activeSession.id);
  }, [activeSession?.id, activeSession?.steps.length]);

  const sidebarItems = useMemo<SessionItemData[]>(
    () => sessionList.map(toSidebarItem),
    [sessionList],
  );

  if (readyState === "loading") {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: TOKENS.bg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          color: TOKENS.textFaint,
        }}
      >
        Loading…
      </div>
    );
  }

  if (readyState === "first-run") {
    return <SettingsView />;
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background:
          "radial-gradient(ellipse at top, #1a1a1a 0%, #050505 60%)",
        padding: 18,
        display: "flex",
        alignItems: "stretch",
        justifyContent: "center",
        boxSizing: "border-box",
      }}
    >
      <WindowFrame onSettingsClick={() => setShowSettings(true)}>
        <SessionList
          sessions={sidebarItems}
          activeId={activeSession?.id ?? null}
          accent={ACCENT}
          glow
          modelLabel="okdoit"
          versionLabel="v0.5"
          onSelect={setActive}
          onNew={() => setActive(null)}
        />
        <CenterPane
          activeSession={activeSession}
          task={task}
          onTaskChange={setTask}
          density="regular"
          monoLogs
          showThinking
          accent={ACCENT}
        />
        <ResultPane
          session={activeSession}
          collapsed={resultCollapsed}
          onToggle={() => setResultCollapsed((v) => !v)}
        />
        {showSettings && (
          <SettingsModal onClose={() => setShowSettings(false)} />
        )}
      </WindowFrame>
    </div>
  );
}

/** ``SessionData`` 를 사이드바 항목 형태로 압축. */
function toSidebarItem(s: SessionData): SessionItemData {
  return {
    id: s.id,
    title: s.task || "(untitled)",
    status: toStatusKey(s.status),
    elapsed: Math.max(0, Math.floor((Date.now() - s.startedAt) / 1000)),
  };
}

function toStatusKey(status: SessionData["status"]): StatusKey {
  if (status === "running") return "running";
  if (status === "paused") return "paused";
  if (status === "errored" || status === "stopped") return "failed";
  if (status === "finished") return "done";
  return "idle";
}
