import { useEffect, useRef } from "react";
import type { StepEntry, StepKind } from "@/stores/sessionStore";

const KIND_LABEL: Record<StepKind, string> = {
  thinking: "Think",
  acted: "Act",
  observed: "Observe",
  verified: "Verify",
};

const KIND_COLOR: Record<StepKind, string> = {
  thinking: "text-purple-700 bg-purple-50",
  acted: "text-blue-700 bg-blue-50",
  observed: "text-gray-700 bg-gray-100",
  verified: "text-emerald-700 bg-emerald-50",
};

interface Props {
  steps: StepEntry[];
}

/**
 * 그래프 노드의 단계별 결과를 시간 순으로 보여준다.
 *
 * 새 항목이 추가될 때 마지막 줄로 자동 스크롤한다(채팅 UX 와 동일).
 */
export function StepLog({ steps }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [steps.length]);

  if (steps.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-gray-300 px-3 py-6 text-center text-xs text-gray-400">
        실행 로그가 여기에 표시됩니다.
      </div>
    );
  }

  return (
    <div className="max-h-[420px] overflow-y-auto rounded-md border border-gray-200 bg-white">
      <ul className="divide-y divide-gray-100">
        {steps.map((step) => (
          <li key={step.id} className="px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${KIND_COLOR[step.kind]}`}
              >
                {KIND_LABEL[step.kind]}
              </span>
              <span className="text-xs text-gray-400">#{step.iteration}</span>
            </div>
            <div className="mt-1 break-words text-gray-800">{step.summary}</div>
          </li>
        ))}
      </ul>
      <div ref={bottomRef} />
    </div>
  );
}
