import { useSession } from "@/stores/sessionStore";
import { useEventStream } from "@/ws/useEventStream";
import { TaskInput } from "@/components/TaskInput";
import { StatusBadge } from "@/components/StatusBadge";
import { PlanChecklist } from "@/components/PlanChecklist";
import { StepLog } from "@/components/StepLog";
import { ResultPanel } from "@/components/ResultPanel";

/**
 * v0.1 1-pane UI.
 *
 * 위에서 아래 순으로:
 *   - 상단 바 (제목 + 상태 배지)
 *   - 작업 입력창 (idle / finished / errored / stopped 일 때만 활성)
 *   - 계획 체크리스트
 *   - 실행 로그
 *   - 결과 / 에러 패널
 *
 * 본격 3-pane 레이아웃 (세션 리스트 + 활동 + 브라우저 미리보기) 은 v0.3 / v0.5 이후.
 */

const INPUT_ENABLED_STATES = new Set([
  "idle",
  "finished",
  "errored",
  "stopped",
]);

export default function App() {
  const sessionId = useSession((s) => s.sessionId);
  const status = useSession((s) => s.status);
  const task = useSession((s) => s.task);
  const subtasks = useSession((s) => s.subtasks);
  const activeIndex = useSession((s) => s.activeSubtaskIndex);
  const steps = useSession((s) => s.steps);
  const result = useSession((s) => s.result);
  const error = useSession((s) => s.error);
  const iterations = useSession((s) => s.iterations);

  useEventStream(sessionId);

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-5 px-6 py-8">
      <header className="flex items-baseline justify-between border-b border-gray-200 pb-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">okdoit</h1>
          <p className="mt-0.5 text-xs text-gray-500">
            자연어 목표를 입력하면 브라우저가 알아서 합니다 (v0.1)
          </p>
        </div>
        <StatusBadge status={status} />
      </header>

      <section>
        <TaskInput enabled={INPUT_ENABLED_STATES.has(status)} />
      </section>

      {task && (
        <section className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            작업
          </span>
          <div className="mt-1 break-words">{task}</div>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">계획</h2>
        <PlanChecklist subtasks={subtasks} activeIndex={activeIndex} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">실행 로그</h2>
        <StepLog steps={steps} />
      </section>

      <ResultPanel result={result} error={error} iterations={iterations} />
    </div>
  );
}
