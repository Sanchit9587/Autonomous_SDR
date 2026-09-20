import { useEffect, useState } from "react";
import { repApi } from "../../api/rep";
import type { AgentDecision } from "../../types";
import { RepCard, repTheme as t } from "../../components/RepLayout";

const verdictColor: Record<string, string> = {
  qualify: "#16a34a", reject: "#dc2626", escalate: "#b45309",
  send: "#0d9488", wait: "#64748b", continue: "#0d9488", needs_review: "#b45309",
};

export function LiveActivity() {
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => repApi.activity(undefined, 80).then(setDecisions).catch((e) => setError(String(e.message)));

  useEffect(() => {
    load();
    // Poll every 5s for a "live" feel (SSE/websocket is a future upgrade).
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ maxWidth: 820 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ color: "#0f4a44", fontSize: 20, fontWeight: 700, margin: 0 }}>Live Activity</h1>
        <span style={{ color: "#0f4a44", fontSize: 10, display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#16a34a" }} /> auto-refreshing
        </span>
      </div>
      {error && <div style={{ color: "#dc2626", fontSize: 12, marginBottom: 12 }}>{error}</div>}
      <RepCard>
        {decisions.length === 0 ? (
          <div style={{ color: t.textMuted, fontSize: 13 }}>No agent activity yet. Run Research/Personalize on a prospect.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {decisions.map((d, i) => (
              <div key={d.id} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "10px 0", borderBottom: i < decisions.length - 1 ? "1px solid rgba(0,0,0,0.06)" : "none" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: verdictColor[d.verdict] ?? t.textFaint, marginTop: 5, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={{ color: t.text, fontSize: 11, fontWeight: 700, textTransform: "capitalize" }}>{d.agent_name}</span>
                    <span style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", color: verdictColor[d.verdict] ?? t.textFaint }}>{d.verdict}</span>
                    <span style={{ flex: 1 }} />
                    <span style={{ color: t.textFaint, fontSize: 10 }}>{new Date(d.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div style={{ color: t.textMuted, fontSize: 11, marginTop: 2 }}>{d.reasoning}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </RepCard>
    </div>
  );
}