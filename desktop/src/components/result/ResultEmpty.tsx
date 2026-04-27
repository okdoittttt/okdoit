/** 세션이 아직 종료되지 않았을 때 우측 패널이 보여주는 placeholder. */

import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";

export function ResultEmpty() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        textAlign: "center",
        color: TOKENS.textFaint,
        fontSize: 12,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 8,
          border: `1px dashed ${TOKENS.borderStrong}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 12,
        }}
      >
        <Icon name="corner" size={16} color={TOKENS.textFaint} />
      </div>
      <div style={{ color: TOKENS.textDim }}>No result yet</div>
      <div style={{ marginTop: 4 }}>
        The artifact will appear here when the agent finishes.
      </div>
    </div>
  );
}
