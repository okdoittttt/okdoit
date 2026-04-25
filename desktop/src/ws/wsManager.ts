/**
 * 멀티 세션 WebSocket 연결 관리자.
 *
 * v0.3 부터 동시 여러 세션의 이벤트를 받아야 한다. 각 세션마다 별도 WS 연결을 두고,
 * 들어오는 이벤트를 모두 ``useSessions.getState().applyEvent`` 로 흘려보낸다.
 * store 의 reducer 가 ``event.session_id`` 로 라우팅하므로 매니저는 어느 이벤트가
 * 어느 세션 것인지 신경 쓰지 않는다.
 *
 * 라이프사이클:
 *   - ``connect(sessionId)`` — store.startSession 직후 호출.
 *   - 자동 종료 — backend 의 ``close_stream()`` 후 ws.onclose 가 트리거되어
 *     매니저 내부 맵에서 자동 제거된다.
 *   - ``disconnect(sessionId)`` — 강제 종료가 필요할 때.
 *   - ``disconnectAll()`` — 앱 종료 시.
 */

import { useSessions } from "@/stores/sessionStore";
import type { ServerEvent } from "@/types/events";

class WsManager {
  private connections = new Map<string, WebSocket>();

  /**
   * 세션 이벤트 스트림에 연결한다. 이미 연결돼 있으면 no-op.
   */
  connect(sessionId: string): void {
    if (this.connections.has(sessionId)) return;

    const url = `${window.okdoit.wsUrl}/sessions/${sessionId}/events`;
    const ws = new WebSocket(url);

    ws.onmessage = (e: MessageEvent<string>) => {
      try {
        const event = JSON.parse(e.data) as ServerEvent;
        useSessions.getState().applyEvent(event);
      } catch (err) {
        console.error("[ws] 메시지 파싱 실패:", err, e.data);
      }
    };

    ws.onerror = (e) => console.error(`[ws ${sessionId}] error:`, e);

    ws.onclose = (e) => {
      console.log(`[ws ${sessionId}] closed code=${e.code} reason=${e.reason}`);
      this.connections.delete(sessionId);
    };

    this.connections.set(sessionId, ws);
  }

  /**
   * 명시적으로 연결을 끊는다.
   */
  disconnect(sessionId: string): void {
    const ws = this.connections.get(sessionId);
    if (!ws) return;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
    this.connections.delete(sessionId);
  }

  /**
   * 모든 연결을 닫는다(앱 종료 시).
   */
  disconnectAll(): void {
    for (const sessionId of Array.from(this.connections.keys())) {
      this.disconnect(sessionId);
    }
  }

  /** 현재 활성 연결 수(테스트 / 디버깅 용도). */
  size(): number {
    return this.connections.size;
  }
}

export const wsManager = new WsManager();
