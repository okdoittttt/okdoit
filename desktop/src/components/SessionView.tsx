import type { SessionData } from "@/stores/sessionStore";
import { StatusBadge } from "@/components/StatusBadge";
import { ControlButtons } from "@/components/ControlButtons";
import { PlanChecklist } from "@/components/PlanChecklist";
import { StepLog } from "@/components/StepLog";
import { ResultPanel } from "@/components/ResultPanel";

interface Props {
  session: SessionData;
}

/**
 * 활성 세션의 상세 화면.
 *
 * 위에서 아래 순으로:
 *   - 헤더 (작업 텍스트 + 상태 배지 + 실행 제어)
 *   - 계획 체크리스트
 *   - 실행 로그
 *   - 결과 / 에러 패널
 */
export function SessionView({ session }: Props) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-8">
      <header className="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
        <div className="min-w-0 flex-1">
          <h1 className="break-words text-base font-semibold text-gray-900">
            {session.task}
          </h1>
          <p className="mt-1 text-xs text-gray-500">반복 {session.iterations}회</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusBadge status={session.status} />
          <ControlButtons sessionId={session.id} status={session.status} />
        </div>
      </header>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">계획</h2>
        <PlanChecklist
          subtasks={session.subtasks}
          activeIndex={session.activeSubtaskIndex}
          replanFlash={session.replanFlash}
          sessionId={session.id}
        />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">실행 로그</h2>
        <StepLog steps={session.steps} />
      </section>

      <ResultPanel
        sessionId={session.id}
        task={session.task}
        status={session.status}
        result={session.result}
        error={session.error}
        iterations={session.iterations}
      />
    </div>
  );
}
