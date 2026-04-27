/** artifact.screenshots 전체를 그리드로 보여주는 탭. */

import { TOKENS } from "@/styles/tokens";
import { resolveSidecarUrl } from "@/lib/api";

interface Props {
  screenshots: string[];
}

export function ScreenshotsTab({ screenshots }: Props) {
  if (screenshots.length === 0) {
    return (
      <div
        style={{
          fontSize: 12,
          color: TOKENS.textFaint,
          fontStyle: "italic",
          padding: "12px 0",
        }}
      >
        (no screenshots captured)
      </div>
    );
  }
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 8,
      }}
    >
      {screenshots.map((rel, i) => {
        const src = resolveSidecarUrl(rel);
        return (
          <a
            key={rel}
            href={src}
            target="_blank"
            rel="noreferrer"
            title={rel}
            style={{
              display: "block",
              borderRadius: 6,
              overflow: "hidden",
              border: `1px solid ${TOKENS.border}`,
              background: "#0F1115",
              transition: "border 0.15s",
            }}
          >
            <img
              src={src}
              alt={`Step ${i + 1}`}
              loading="lazy"
              style={{
                width: "100%",
                height: 88,
                objectFit: "cover",
                display: "block",
              }}
            />
          </a>
        );
      })}
    </div>
  );
}
