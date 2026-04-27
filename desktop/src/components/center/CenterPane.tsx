/**
 * 가운데 패널 컨테이너.
 *
 * 활성 세션이 없으면 idle 상태(빈 활동 로그) + 작업 입력창을, 있으면 해당
 * 세션의 status / steps 를 ActivityLog 에 흘려 보여준다.
 */

import { TOKENS, type StatusKey } from "@/styles/tokens";
import type { SessionData } from "@/stores/sessionStore";
import { TaskInputBox } from "./TaskInputBox";
import { ActivityLog } from "./ActivityLog";

interface Props {
  activeSession: SessionData | null;
  task: string;
  onTaskChange: (next: string) => void;
  density: "compact" | "regular" | "comfy";
  monoLogs: boolean;
  showThinking: boolean;
  accent: string;
}

/** backend ``SessionStatus`` 를 디자인의 ``StatusKey`` 로 변환. */
function toStatusKey(status: SessionData["status"] | null): StatusKey {
  if (status === null) return "idle";
  if (status === "running") return "running";
  if (status === "paused") return "paused";
  if (status === "errored" || status === "stopped") return "failed";
  if (status === "finished") return "done";
  return "idle";
}

export function CenterPane({
  activeSession,
  task,
  onTaskChange,
  density,
  monoLogs,
  showThinking,
  accent,
}: Props) {
  const statusKey = toStatusKey(activeSession?.status ?? null);

  // 진행/일시정지 중인 세션은 textarea 가 잠기므로 해당 세션의 task 를 노출,
  // 그 외에는 사용자가 입력 중인 로컬 task 를 그대로 노출한다.
  const isRunning =
    activeSession?.status === "running" || activeSession?.status === "paused";
  const displayedTask = isRunning ? activeSession.task : task;

  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        background: TOKENS.bg,
        minWidth: 0,
      }}
    >
      <TaskInputBox
        status={activeSession?.status ?? null}
        activeSessionId={activeSession?.id ?? null}
        task={displayedTask}
        onTaskChange={onTaskChange}
        accent={accent}
      />
      <ActivityLog
        steps={activeSession?.steps ?? []}
        status={statusKey}
        sessionStartedAt={activeSession?.startedAt ?? Date.now()}
        density={density}
        monoLogs={monoLogs}
        showThinking={showThinking}
        accent={accent}
      />
    </main>
  );
}
