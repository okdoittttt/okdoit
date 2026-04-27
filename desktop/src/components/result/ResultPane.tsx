/**
 * 우측 312px 패널(접으면 38px). Markdown / JSON / Screenshots 3 탭 + 최신
 * 스크린샷 미리보기 + 복사 버튼.
 *
 * 세션이 종료(finished/errored/stopped)된 뒤에만 ``getArtifact`` 를 한 번 부른다.
 * 진행 중에는 ResultEmpty placeholder 를 띄운다.
 */

import { useEffect, useState } from "react";
import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import { iconBtn } from "@/components/common/buttonStyles";
import { StatusBadge } from "@/components/common/StatusBadge";
import { getArtifact } from "@/lib/api";
import type { SessionArtifact } from "@/types/artifact";
import type { SessionData, SessionStatus } from "@/stores/sessionStore";
import { ResultEmpty } from "./ResultEmpty";
import { ScreenshotPreview } from "./ScreenshotPreview";
import { MarkdownView } from "./MarkdownView";
import { JsonView } from "./JsonView";
import { ScreenshotsTab } from "./ScreenshotsTab";

type Tab = "markdown" | "json" | "screenshots";

const TABS: { id: Tab; label: string }[] = [
  { id: "markdown", label: "Markdown" },
  { id: "json", label: "JSON" },
  { id: "screenshots", label: "Screenshots" },
];

const TERMINAL: ReadonlySet<SessionStatus> = new Set([
  "finished",
  "errored",
  "stopped",
]);

interface Props {
  session: SessionData | null;
  collapsed: boolean;
  onToggle: () => void;
}

export function ResultPane({ session, collapsed, onToggle }: Props) {
  const [tab, setTab] = useState<Tab>("markdown");
  const [copied, setCopied] = useState(false);
  const [artifact, setArtifact] = useState<SessionArtifact | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);

  const status = session?.status ?? null;
  const isTerminal = status !== null && TERMINAL.has(status);
  const isDone = status === "finished";

  useEffect(() => {
    if (!session || !isTerminal) {
      setArtifact(null);
      setArtifactError(null);
      return;
    }
    let cancelled = false;
    getArtifact(session.id)
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
  }, [session?.id, isTerminal]);

  if (collapsed) {
    return (
      <aside
        style={{
          width: 38,
          flexShrink: 0,
          background: "#0A0A0A",
          borderLeft: `1px solid ${TOKENS.border}`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "12px 0",
        }}
      >
        <button
          type="button"
          onClick={onToggle}
          title="Show result"
          style={{
            width: 28,
            height: 28,
            padding: 0,
            background: "transparent",
            border: `1px solid ${TOKENS.border}`,
            borderRadius: 6,
            color: TOKENS.textDim,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span style={{ transform: "rotate(90deg)", display: "inline-flex" }}>
            <Icon name="chev" size={12} />
          </span>
        </button>
        <div
          style={{
            marginTop: 14,
            writingMode: "vertical-rl",
            transform: "rotate(180deg)",
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: 1,
            color: TOKENS.textFaint,
            textTransform: "uppercase",
          }}
        >
          Result
        </div>
        {isDone && (
          <div
            style={{
              marginTop: 10,
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: TOKENS.success,
            }}
          />
        )}
      </aside>
    );
  }

  async function handleCopy(): Promise<void> {
    if (!session) return;
    const text =
      tab === "json"
        ? JSON.stringify(
            artifact ?? {
              task: session.task,
              result: session.result,
              error: session.error,
              iterations: session.iterations,
            },
            null,
            2,
          )
        : (session.result ?? session.error ?? "");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* noop */
    }
  }

  return (
    <aside
      style={{
        width: 312,
        flexShrink: 0,
        background: "#0A0A0A",
        borderLeft: `1px solid ${TOKENS.border}`,
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
      }}
    >
      <div
        style={{
          padding: "12px 14px",
          borderBottom: `1px solid ${TOKENS.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            minWidth: 0,
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 13,
              fontWeight: 600,
              color: TOKENS.text,
            }}
          >
            Result
          </h2>
          {isDone && <StatusBadge status="done" />}
          {status === "errored" && <StatusBadge status="failed" />}
        </div>
        <button
          type="button"
          onClick={onToggle}
          title="Hide result"
          style={{
            width: 24,
            height: 24,
            padding: 0,
            background: "transparent",
            border: `1px solid ${TOKENS.border}`,
            borderRadius: 5,
            color: TOKENS.textDim,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <span style={{ transform: "rotate(-90deg)", display: "inline-flex" }}>
            <Icon name="chev" size={11} />
          </span>
        </button>
      </div>

      {!session || !isTerminal ? (
        <ResultEmpty />
      ) : (
        <>
          <ScreenshotPreview screenshots={artifact?.screenshots ?? []} />

          <div
            style={{
              padding: "12px 16px 0",
              display: "flex",
              gap: 4,
            }}
          >
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                style={{
                  height: 26,
                  padding: "0 10px",
                  background: tab === t.id ? TOKENS.surface : "transparent",
                  border: `1px solid ${tab === t.id ? TOKENS.borderStrong : "transparent"}`,
                  borderRadius: 6,
                  color: tab === t.id ? TOKENS.text : TOKENS.textDim,
                  fontSize: 12,
                  fontWeight: 500,
                  fontFamily: "inherit",
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            {tab !== "screenshots" && (
              <button
                type="button"
                onClick={() => void handleCopy()}
                style={iconBtn(copied)}
              >
                <Icon name={copied ? "check" : "copy"} size={11} />
                <span style={{ marginLeft: 4 }}>
                  {copied ? "Copied" : "Copy"}
                </span>
              </button>
            )}
          </div>

          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "12px 16px 18px",
            }}
          >
            {artifactError && (
              <div
                style={{
                  marginBottom: 10,
                  padding: "8px 10px",
                  borderRadius: 6,
                  background: `${TOKENS.warn}1A`,
                  border: `1px solid ${TOKENS.warn}33`,
                  color: TOKENS.warn,
                  fontSize: 11.5,
                  lineHeight: 1.4,
                }}
              >
                Artifact fetch failed: {artifactError}
              </div>
            )}
            {tab === "markdown" && (
              <MarkdownView
                result={session.result}
                error={session.error}
              />
            )}
            {tab === "json" && (
              <JsonView
                artifact={artifact}
                fallback={{
                  task: session.task,
                  result: session.result,
                  error: session.error,
                  iterations: session.iterations,
                }}
              />
            )}
            {tab === "screenshots" && (
              <ScreenshotsTab screenshots={artifact?.screenshots ?? []} />
            )}
          </div>
        </>
      )}
    </aside>
  );
}
