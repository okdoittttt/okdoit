/**
 * 우측 패널 상단의 "Final browser state" 미리보기.
 *
 * artifact.screenshots 의 가장 마지막 항목을 sidecar URL 로 풀어 ``<img>`` 로
 * 그린다. 스크린샷이 없으면 dashed border placeholder.
 */

import { useState } from "react";
import { FONT_MONO, TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";
import { resolveSidecarUrl } from "@/lib/api";

interface Props {
  screenshots: string[];
}

export function ScreenshotPreview({ screenshots }: Props) {
  const latest = screenshots.length > 0 ? screenshots[screenshots.length - 1] : null;

  return (
    <div
      style={{
        padding: 16,
        borderBottom: `1px solid ${TOKENS.border}`,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: 0.8,
          color: TOKENS.textFaint,
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        Final browser state
      </div>
      {latest ? <Thumb src={resolveSidecarUrl(latest)} /> : <ThumbPlaceholder />}
    </div>
  );
}

function Thumb({ src }: { src: string }) {
  const [errored, setErrored] = useState(false);
  if (errored) return <ThumbPlaceholder />;
  return (
    <a
      href={src}
      target="_blank"
      rel="noreferrer"
      style={{
        display: "block",
        width: "100%",
        aspectRatio: "16 / 10",
        background: "#0F1115",
        border: `1px solid ${TOKENS.border}`,
        borderRadius: 7,
        overflow: "hidden",
      }}
    >
      <img
        src={src}
        alt="Latest screenshot"
        loading="lazy"
        onError={() => setErrored(true)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />
    </a>
  );
}

function ThumbPlaceholder() {
  return (
    <div
      style={{
        width: "100%",
        aspectRatio: "16 / 10",
        background: "#0F1115",
        border: `1px dashed ${TOKENS.borderStrong}`,
        borderRadius: 7,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        color: TOKENS.textFaint,
        fontFamily: FONT_MONO,
        fontSize: 10.5,
      }}
    >
      <Icon name="globe" size={20} color={TOKENS.textFaint} />
      <span>no screenshot</span>
    </div>
  );
}
