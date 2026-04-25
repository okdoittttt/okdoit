/**
 * sidecar WebSocket 이벤트 스트림을 ``sessionStore`` 에 연결하는 React 훅.
 *
 * 사용:
 *   ``useEventStream(sessionId)`` 를 한 컴포넌트에서 호출하면 자동으로 WS 를 열고
 *   이벤트를 store 의 ``applyEvent`` 로 흘려보낸다. 컴포넌트 unmount 또는 sessionId
 *   변경 시 이전 연결은 정리된다.
 *
 * 한 세션에 한 연결을 가정한다(서버도 동일).
 */

import { useEffect } from "react";
import { useSession } from "@/stores/sessionStore";
import type { ServerEvent } from "@/types/events";

/**
 * sessionId 가 ``null`` 이면 아무것도 하지 않는다(세션 시작 전 상태).
 */
export function useEventStream(sessionId: string | null): void {
  const applyEvent = useSession((s) => s.applyEvent);

  useEffect(() => {
    if (!sessionId) return;

    const url = `${window.okdoit.wsUrl}/sessions/${sessionId}/events`;
    const ws = new WebSocket(url);

    ws.onmessage = (e: MessageEvent<string>) => {
      try {
        const event = JSON.parse(e.data) as ServerEvent;
        applyEvent(event);
      } catch (err) {
        console.error("[ws] 메시지 파싱 실패:", err, e.data);
      }
    };

    ws.onerror = (e) => {
      console.error("[ws] error:", e);
    };

    ws.onclose = (e) => {
      console.log(`[ws] closed code=${e.code} reason=${e.reason}`);
    };

    return () => {
      // unmount 또는 sessionId 변경 시 깨끗하게 닫는다.
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [sessionId, applyEvent]);
}
