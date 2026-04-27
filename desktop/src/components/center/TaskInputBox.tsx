/**
 * 가운데 패널 상단의 작업 입력창.
 *
 * 현재 active 세션이 없거나 종료된 상태(idle/finished/errored/stopped)일 때만
 * textarea 가 활성. 진행 중(running/paused)이면 입력은 잠기고 컨트롤 버튼만
 * 노출된다.
 *
 * 동작:
 *   - Run: ``postRun`` → ``startSession`` → ``wsManager.connect``.
 *   - Pause / Resume / Stop: ``postPause`` / ``postResume`` / ``postStop`` 호출.
 */

import { useState } from "react";
import { FONT_MONO, FONT_SANS, TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import {
  dangerBtn,
  ghostBtn,
  kbdStyle,
  primaryBtn,
} from "@/components/common/buttonStyles";
import { postPause, postResume, postRun, postStop } from "@/lib/api";
import { useSessions, type SessionStatus } from "@/stores/sessionStore";
import { wsManager } from "@/ws/wsManager";

interface Props {
  /** 현재 화면에 보여지는 세션의 상태. 세션이 없으면 ``null``. */
  status: SessionStatus | null;
  /** 활성 세션 id. 컨트롤 버튼이 호출할 때 필요. 없으면 ``null``. */
  activeSessionId: string | null;
  task: string;
  onTaskChange: (next: string) => void;
  accent: string;
}

const KBD_DARK = {
  ...kbdStyle,
  background: "rgba(0,0,0,0.25)",
  border: "1px solid rgba(255,255,255,0.15)",
  color: "#fff",
};

export function TaskInputBox({
  status,
  activeSessionId,
  task,
  onTaskChange,
  accent,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [pendingAction, setPendingAction] = useState<
    "pause" | "resume" | "stop" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const startSession = useSessions((s) => s.startSession);

  const isRunning = status === "running";
  const isPaused = status === "paused";
  const inputDisabled = isRunning || isPaused || submitting;
  const canRun = !inputDisabled && task.trim().length > 0;

  async function runTask(): Promise<void> {
    if (!canRun) return;
    const text = task.trim();
    setSubmitting(true);
    setError(null);
    try {
      const res = await postRun({ task: text, headless: false });
      startSession(res.session_id, text);
      wsManager.connect(res.session_id);
      onTaskChange("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function callAction(action: "pause" | "resume" | "stop"): Promise<void> {
    if (!activeSessionId) return;
    setPendingAction(action);
    setError(null);
    try {
      if (action === "pause") await postPause(activeSessionId);
      else if (action === "resume") await postResume(activeSessionId);
      else await postStop(activeSessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div
      style={{
        padding: "16px 20px 14px",
        borderBottom: `1px solid ${TOKENS.border}`,
      }}
    >
      <div
        style={{
          background: TOKENS.surface,
          border: `1px solid ${TOKENS.border}`,
          borderRadius: 10,
          padding: 14,
          transition: "border 0.15s",
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: 0.9,
            color: TOKENS.textFaint,
            textTransform: "uppercase",
            marginBottom: 8,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Icon name="spark" size={11} color={accent} />
          Task
        </div>
        <textarea
          value={task}
          onChange={(e) => onTaskChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void runTask();
            }
          }}
          placeholder="Describe what you want the agent to do…"
          disabled={inputDisabled}
          style={{
            width: "100%",
            minHeight: 52,
            maxHeight: 140,
            background: "transparent",
            border: 0,
            outline: 0,
            resize: "vertical",
            color: TOKENS.text,
            fontSize: 14,
            fontFamily: FONT_SANS,
            lineHeight: 1.5,
            padding: 0,
          }}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginTop: 10,
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: TOKENS.textFaint,
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontFamily: FONT_MONO,
            }}
          >
            <Icon name="cmd" size={11} />
            Use natural language
          </span>
          <div style={{ flex: 1 }} />
          {!isRunning && !isPaused && (
            <button
              type="button"
              onClick={() => void runTask()}
              disabled={!canRun}
              style={{
                ...primaryBtn(accent),
                opacity: canRun ? 1 : 0.5,
                cursor: canRun ? "pointer" : "not-allowed",
              }}
            >
              <Icon name="play" size={11} color="#fff" />
              <span>{submitting ? "Starting…" : "Run"}</span>
              <span
                style={{
                  display: "flex",
                  gap: 3,
                  marginLeft: 6,
                  opacity: 0.85,
                }}
              >
                <kbd style={KBD_DARK}>⌘</kbd>
                <kbd style={KBD_DARK}>⏎</kbd>
              </span>
            </button>
          )}
          {isRunning && (
            <>
              <button
                type="button"
                onClick={() => void callAction("pause")}
                disabled={pendingAction !== null}
                style={{
                  ...ghostBtn(),
                  opacity: pendingAction ? 0.5 : 1,
                }}
              >
                <Icon name="pause" size={11} />
                <span>{pendingAction === "pause" ? "…" : "Pause"}</span>
              </button>
              <button
                type="button"
                onClick={() => void callAction("stop")}
                disabled={pendingAction !== null}
                style={{
                  ...dangerBtn(),
                  opacity: pendingAction ? 0.5 : 1,
                }}
              >
                <Icon name="stop" size={11} />
                <span>{pendingAction === "stop" ? "…" : "Stop"}</span>
              </button>
            </>
          )}
          {isPaused && (
            <>
              <button
                type="button"
                onClick={() => void callAction("resume")}
                disabled={pendingAction !== null}
                style={{
                  ...primaryBtn(accent),
                  opacity: pendingAction ? 0.5 : 1,
                }}
              >
                <Icon name="play" size={11} color="#fff" />
                <span>{pendingAction === "resume" ? "…" : "Resume"}</span>
              </button>
              <button
                type="button"
                onClick={() => void callAction("stop")}
                disabled={pendingAction !== null}
                style={{
                  ...dangerBtn(),
                  opacity: pendingAction ? 0.5 : 1,
                }}
              >
                <Icon name="stop" size={11} />
                <span>{pendingAction === "stop" ? "…" : "Stop"}</span>
              </button>
            </>
          )}
        </div>
        {error && (
          <div
            style={{
              marginTop: 10,
              padding: "8px 10px",
              borderRadius: 6,
              background: `${TOKENS.error}1A`,
              border: `1px solid ${TOKENS.error}33`,
              color: TOKENS.error,
              fontSize: 11.5,
              lineHeight: 1.4,
            }}
          >
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
