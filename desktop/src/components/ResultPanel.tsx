import { useEffect, useState } from "react";
import { getArtifact, resolveSidecarUrl } from "@/lib/api";
import type { SessionArtifact } from "@/types/artifact";
import type { SessionStatus } from "@/stores/sessionStore";

interface Props {
  sessionId: string;
  task: string;
  status: SessionStatus;
  result: string | null;
  error: string | null;
  iterations: number;
}

const COPY_FEEDBACK_MS = 1500;
const TERMINAL_STATES: ReadonlySet<SessionStatus> = new Set([
  "finished",
  "errored",
  "stopped",
]);

/**
 * 세션 종료 후 결과 패널.
 *
 * 진행 중에는 렌더하지 않는다. 종료 상태(finished/errored/stopped) 가 되면:
 *   - 결과 또는 에러 텍스트
 *   - 마크다운 / JSON 복사 버튼
 *   - 아티팩트 조회 시도 → 스크린샷 갤러리 + 추출 데이터 테이블
 *
 * 아티팩트는 sidecar 의 ``/sessions/{id}/artifact`` 응답이라 비동기로 채워진다.
 */
export function ResultPanel({ sessionId, task, status, result, error, iterations }: Props) {
  const [artifact, setArtifact] = useState<SessionArtifact | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);

  const isTerminal = TERMINAL_STATES.has(status);

  useEffect(() => {
    if (!isTerminal) {
      setArtifact(null);
      setArtifactError(null);
      return;
    }

    let cancelled = false;
    getArtifact(sessionId)
      .then((a) => {
        if (!cancelled) setArtifact(a);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setArtifactError(err instanceof Error ? err.message : String(err));
      });

    return () => {
      cancelled = true;
    };
  }, [isTerminal, sessionId]);

  if (!isTerminal) return null;

  const tone = error ? "red" : "emerald";
  const toneClasses =
    tone === "red"
      ? "border-red-200 bg-red-50"
      : "border-emerald-200 bg-emerald-50";
  const labelTone = tone === "red" ? "text-red-700" : "text-emerald-700";

  return (
    <div className="space-y-4">
      <div className={`rounded-md border ${toneClasses} px-4 py-3`}>
        <div className="flex items-center justify-between">
          <div className={`text-xs font-semibold uppercase tracking-wide ${labelTone}`}>
            {error ? "오류" : "결과"}
          </div>
          <ExportButtons
            task={task}
            result={result}
            error={error}
            iterations={iterations}
            artifact={artifact}
          />
        </div>
        <div className="mt-1 whitespace-pre-wrap break-words text-sm text-gray-900">
          {error ?? result ?? "(결과 없음)"}
        </div>
        <div className={`mt-2 text-xs ${tone === "red" ? "text-red-500" : "text-emerald-600"}`}>
          반복 {iterations}회{error ? " 후 종료" : ""}
        </div>
      </div>

      {artifactError && (
        <div className="rounded-md bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
          아티팩트 조회 실패: {artifactError}
        </div>
      )}

      {artifact && artifact.screenshots.length > 0 && (
        <ScreenshotGallery screenshots={artifact.screenshots} />
      )}

      {artifact && Object.keys(artifact.collected_data).length > 0 && (
        <CollectedDataTable data={artifact.collected_data} />
      )}
    </div>
  );
}

// ── 내보내기 / 복사 ────────────────────────────────────────────

interface ExportProps {
  task: string;
  result: string | null;
  error: string | null;
  iterations: number;
  artifact: SessionArtifact | null;
}

function ExportButtons({ task, result, error, iterations, artifact }: ExportProps) {
  const [copiedKind, setCopiedKind] = useState<"md" | "json" | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);

  async function copy(kind: "md" | "json") {
    setCopyError(null);
    const text =
      kind === "md"
        ? formatMarkdown({ task, result, error, iterations, artifact })
        : formatJson({ task, result, error, iterations, artifact });
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKind(kind);
      window.setTimeout(() => setCopiedKind(null), COPY_FEEDBACK_MS);
    } catch (err) {
      setCopyError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-1.5">
        <button
          type="button"
          onClick={() => void copy("md")}
          className="rounded-md bg-white px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-50"
        >
          {copiedKind === "md" ? "복사됨" : "마크다운 복사"}
        </button>
        <button
          type="button"
          onClick={() => void copy("json")}
          className="rounded-md bg-white px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-50"
        >
          {copiedKind === "json" ? "복사됨" : "JSON 복사"}
        </button>
      </div>
      {copyError && <span className="text-[10px] text-red-600">{copyError}</span>}
    </div>
  );
}

// ── 스크린샷 갤러리 ────────────────────────────────────────────

function ScreenshotGallery({ screenshots }: { screenshots: string[] }) {
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-gray-700">
        스크린샷 ({screenshots.length})
      </h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {screenshots.map((rel) => {
          const src = resolveSidecarUrl(rel);
          return (
            <a
              key={rel}
              href={src}
              target="_blank"
              rel="noreferrer"
              className="block overflow-hidden rounded-md border border-gray-200 transition hover:border-blue-300"
            >
              <img
                src={src}
                alt={rel}
                loading="lazy"
                className="h-32 w-full object-cover"
              />
            </a>
          );
        })}
      </div>
    </section>
  );
}

// ── 추출 데이터 테이블 ─────────────────────────────────────────

function CollectedDataTable({
  data,
}: {
  data: Record<string, { information?: string; collected?: boolean; [k: string]: unknown }>;
}) {
  const entries = Object.entries(data);
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-gray-700">추출 데이터</h2>
      <div className="overflow-hidden rounded-md border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                키
              </th>
              <th className="px-3 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                값
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {entries.map(([key, val]) => (
              <tr key={key}>
                <td className="px-3 py-1.5 align-top font-medium text-gray-700">{key}</td>
                <td className="px-3 py-1.5 break-words text-gray-800">
                  {val.information ?? JSON.stringify(val)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── 포매터 ────────────────────────────────────────────────────

interface FormatInput {
  task: string;
  result: string | null;
  error: string | null;
  iterations: number;
  artifact: SessionArtifact | null;
}

/**
 * 결과를 사람이 읽기 좋은 마크다운 문자열로 변환한다.
 *
 * 클립보드 복사용. 추후 .md 파일 다운로드도 같은 함수를 재사용한다.
 */
function formatMarkdown({ task, result, error, iterations, artifact }: FormatInput): string {
  const lines: string[] = [];
  lines.push(`# ${task}`);
  lines.push("");
  lines.push(`반복 ${iterations}회`);
  lines.push("");
  if (error) {
    lines.push("## 오류");
    lines.push("");
    lines.push(error);
  } else if (result) {
    lines.push("## 결과");
    lines.push("");
    lines.push(result);
  }
  if (artifact) {
    if (artifact.subtasks.length > 0) {
      lines.push("");
      lines.push("## 계획 진행도");
      lines.push("");
      for (const s of artifact.subtasks) {
        lines.push(`- [${s.done ? "x" : " "}] ${s.description}`);
      }
    }
    if (Object.keys(artifact.collected_data).length > 0) {
      lines.push("");
      lines.push("## 추출 데이터");
      lines.push("");
      for (const [key, val] of Object.entries(artifact.collected_data)) {
        const v = val.information ?? JSON.stringify(val);
        lines.push(`- **${key}**: ${v}`);
      }
    }
  }
  return lines.join("\n");
}

function formatJson({ task, result, error, iterations, artifact }: FormatInput): string {
  return JSON.stringify(
    {
      task,
      iterations,
      result,
      error,
      artifact,
    },
    null,
    2,
  );
}
