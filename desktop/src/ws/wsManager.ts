/**
 * 멀티 세션 WebSocket 연결 관리자.
 *
 * v0.3 부터 동시 여러 세션의 이벤트를 받아야 한다. 각 세션마다 별도 WS 연결을 두고,
 * 들어오는 이벤트를 모두 ``useSessions.getState().applyEvent`` 로 흘려보낸다.
 * store 의 reducer 가 ``event.session_id`` 로 라우팅하므로 매니저는 어느 이벤트가
 * 어느 세션 것인지 신경 쓰지 않는다.
 *
 * PR3 부터 sidecar 는 ``WireMessage`` envelope (`{seq, event}`) 을 보낸다.
 * PR4 부터 매니저는 마지막 수신 ``seq`` 를 메모리 + ``localStorage`` 에 보관해
 * 재연결 시 ``?since_seq=<n>`` 쿼리로 누락분 복원을 받는다. 종료 이벤트 수신
 * 시점에는 lastSeq 를 비워 다시 같은 세션에 연결할 일이 없도록 한다.
 *
 * 라이프사이클:
 *   - ``connect(sessionId)`` — store.startSession 직후 호출.
 *   - 자동 종료 — backend 의 ``close_stream()`` 후 ws.onclose 가 트리거되어
 *     매니저 내부 맵에서 자동 제거된다.
 *   - ``disconnect(sessionId)`` — 강제 종료가 필요할 때.
 *   - ``disconnectAll()`` — 앱 종료 시.
 */

import { useSessions } from "@/stores/sessionStore";
import type { ServerEventType, WireMessage } from "@/types/events";

/** localStorage 키 prefix — 세션별 마지막 수신 seq 를 보관. */
const LAST_SEQ_STORAGE_PREFIX = "okdoit:lastSeq:";

/**
 * 도달 시 추가 이벤트가 없는 종료 계열 이벤트.
 * 수신하면 lastSeq 를 잊어 같은 세션 재연결이 헛도는 것을 막는다.
 */
const TERMINAL_EVENT_TYPES: ReadonlySet<ServerEventType> = new Set<ServerEventType>([
  "session.finished",
  "session.errored",
  "session.stopped",
]);

class WsManager {
  private connections = new Map<string, WebSocket>();
  /** 세션별 마지막 수신 seq — 재연결 시 ``?since_seq=`` 쿼리로 보낸다. */
  private lastSeqs = new Map<string, number>();

  /**
   * 세션 이벤트 스트림에 연결한다. 이미 연결돼 있으면 no-op.
   *
   * 같은 세션에 대한 lastSeq 가 메모리 또는 localStorage 에 있으면
   * ``?since_seq=<n>`` 쿼리로 누락분 replay 를 요청한다. 처음 연결이면 쿼리 없이.
   */
  connect(sessionId: string): void {
    if (this.connections.has(sessionId)) return;

    const lastSeq = this.lastSeqs.get(sessionId) ?? loadLastSeq(sessionId);
    let url = `${window.okdoit.wsUrl}/sessions/${sessionId}/events`;
    if (lastSeq !== null) {
      url += `?since_seq=${lastSeq}`;
    }

    const ws = new WebSocket(url);

    ws.onmessage = (e: MessageEvent<string>) => {
      try {
        const wire = JSON.parse(e.data) as WireMessage;
        // seq 갱신 — 메모리 + 영속 저장. 다음 재연결이 이 값을 넘긴다.
        this.lastSeqs.set(sessionId, wire.seq);
        saveLastSeq(sessionId, wire.seq);
        useSessions.getState().applyEvent(wire.event);
        // 종료 이벤트 후엔 더 이상 받을 게 없으니 lastSeq 를 잊는다.
        if (TERMINAL_EVENT_TYPES.has(wire.event.type)) {
          this.lastSeqs.delete(sessionId);
          clearLastSeq(sessionId);
        }
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

// ── localStorage 헬퍼 ──────────────────────────────────────────────
//
// localStorage 는 renderer 에서 항상 접근 가능 (Electron 의 webContents).
// 실패해도(quota / 비활성화) 콘솔 로그만 남기고 동작은 계속 — 메모리 lastSeqs
// 가 fallback 으로 동작한다.

function loadLastSeq(sessionId: string): number | null {
  try {
    const raw = window.localStorage.getItem(LAST_SEQ_STORAGE_PREFIX + sessionId);
    if (raw === null) return null;
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) ? n : null;
  } catch (err) {
    console.warn("[ws] lastSeq 로드 실패:", err);
    return null;
  }
}

function saveLastSeq(sessionId: string, seq: number): void {
  try {
    window.localStorage.setItem(LAST_SEQ_STORAGE_PREFIX + sessionId, String(seq));
  } catch (err) {
    console.warn("[ws] lastSeq 저장 실패:", err);
  }
}

function clearLastSeq(sessionId: string): void {
  try {
    window.localStorage.removeItem(LAST_SEQ_STORAGE_PREFIX + sessionId);
  } catch (err) {
    console.warn("[ws] lastSeq 제거 실패:", err);
  }
}

export const wsManager = new WsManager();
