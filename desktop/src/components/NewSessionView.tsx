import { useState } from "react";
import { TaskInput } from "@/components/TaskInput";
import { TaskTemplates } from "@/components/TaskTemplates";

/**
 * 새 작업 입력 화면.
 *
 * 활성 세션이 없거나, 사용자가 "새 세션" 을 명시적으로 선택했을 때 노출된다.
 * 본격 UI 본문(``SessionView``) 과 분리해서 입력창 관련 상태(textarea, 템플릿 선택)를
 * 이 컴포넌트 안에 가둔다.
 */
export function NewSessionView() {
  const [inputText, setInputText] = useState("");
  const showTemplates = inputText.trim().length === 0;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5 px-6 py-10">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">새 작업</h1>
        <p className="mt-0.5 text-xs text-gray-500">
          자연어로 목표를 입력하세요. 브라우저가 알아서 수행합니다.
        </p>
      </div>

      <TaskInput enabled value={inputText} onChange={setInputText} />

      {showTemplates && (
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            예시 작업
          </h2>
          <TaskTemplates onSelect={setInputText} />
        </section>
      )}
    </div>
  );
}
