import { useEffect, useState } from "react";
import { useActiveSession, useSessionList, useSessions } from "@/stores/sessionStore";
import { wsManager } from "@/ws/wsManager";
import { SessionList } from "@/components/SessionList";
import { NewSessionView } from "@/components/NewSessionView";
import { SessionView } from "@/components/SessionView";
import { SettingsView } from "@/components/SettingsView";

/**
 * v0.4 UX 진입점.
 *
 * 흐름:
 *   1) 부팅 시 ``window.okdoit.settings.status()`` 로 ready 여부 확인.
 *   2) ready=false → ``SettingsView`` 만 노출. 저장하면 main 이 reload 트리거.
 *   3) ready=true  → 기존 2-pane (좌측 SessionList + 우측 NewSession/SessionView).
 *      좌상단 ⚙ 버튼으로 SettingsView 다시 열 수 있다(edit 모드).
 *
 * WS 연결은 ``wsManager`` 가 일괄 관리. startSession 시점에 connect 되고,
 * backend 가 ``close_stream`` 하면 자동 disconnect.
 */

type ReadyState = "loading" | "first-run" | "ready";

export default function App() {
  const [readyState, setReadyState] = useState<ReadyState>("loading");
  const [showSettings, setShowSettings] = useState(false);

  const activeSession = useActiveSession();
  const sessionList = useSessionList();
  const setActive = useSessions((s) => s.setActive);

  // 부팅 시 한 번만 settings 상태 확인.
  useEffect(() => {
    void window.okdoit.settings.status().then(({ ready }) => {
      setReadyState(ready ? "ready" : "first-run");
    });
  }, []);

  // 앱 종료 시 모든 WS 닫기.
  useEffect(() => {
    return () => wsManager.disconnectAll();
  }, []);

  if (readyState === "loading") {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        설정 확인 중…
      </div>
    );
  }

  if (readyState === "first-run") {
    return <SettingsView variant="first-run" />;
  }

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 border-r border-gray-200">
        <SessionList
          sessions={sessionList}
          activeId={activeSession?.id ?? null}
          onSelect={setActive}
        />
      </aside>
      <main className="flex-1 overflow-y-auto bg-white">
        {showSettings ? (
          <SettingsView variant="edit" onClose={() => setShowSettings(false)} />
        ) : activeSession ? (
          <SessionView session={activeSession} />
        ) : (
          <NewSessionView />
        )}
      </main>
      <button
        type="button"
        onClick={() => setShowSettings((v) => !v)}
        title="설정"
        className="fixed right-4 top-4 z-10 rounded-md bg-white px-2 py-1 text-xs text-gray-500 ring-1 ring-gray-200 transition hover:text-gray-800"
      >
        ⚙
      </button>
    </div>
  );
}
