import { useEffect } from "react";
import { useActiveSession, useSessionList, useSessions } from "@/stores/sessionStore";
import { wsManager } from "@/ws/wsManager";
import { SessionList } from "@/components/SessionList";
import { NewSessionView } from "@/components/NewSessionView";
import { SessionView } from "@/components/SessionView";

/**
 * v0.3 2-pane UI.
 *
 * 좌측: 세션 리스트 패널 ``SessionList``
 * 우측: 활성 세션이 있으면 ``SessionView``, 없으면 ``NewSessionView``
 *
 * WS 연결은 ``wsManager`` 가 일괄 관리한다 — startSession 시점에 connect 되고,
 * backend 가 ``close_stream`` 하면 자동 disconnect 된다.
 */

export default function App() {
  const activeSession = useActiveSession();
  const sessionList = useSessionList();
  const setActive = useSessions((s) => s.setActive);

  // 앱 종료 시 모든 WS 닫기.
  useEffect(() => {
    return () => wsManager.disconnectAll();
  }, []);

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
        {activeSession ? <SessionView session={activeSession} /> : <NewSessionView />}
      </main>
    </div>
  );
}
