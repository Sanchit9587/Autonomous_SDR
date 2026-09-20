import { useEffect, useState } from "react";
import { repApi } from "../../api/rep";
import type { AgentDecision } from "../../types";
import { RepCard, repTheme as t } from "../../components/RepLayout";

export function Escalations() {
  const [items, setItems] = useState<AgentDecision[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    repApi.escalations().then(setItems).catch((e) => setError(String(e.message)));
  }, []);

  return (
    <div style={{ maxWidth: 820 }}>
      <h1 style={{ color: "#0f4a44", fontSize: 20, fontWeight: 700, margin: "0 0 16px 0" }}>
        Escalations {items.length > 0 && <span style={{ fontSize: 13, color: "#b45309" }}>· {items.length} open</span>}
      </h1>
      {error && <div style={{ color: "#dc2626", fontSize: 12, marginBottom: 12 }}>{error}</div>}
      {items.length === 0 ? (
        <RepCard><div style={{ color: t.textMuted, fontSize: 13 }}>No escalations. Agents handle everything autonomously right now. 🎉</div></RepCard>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((e) => (
            <RepCard key={e.id} style={{ borderLeft: "3px solid #f59e0b" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ background: "rgba(217,119,6,0.12)", color: "#b45309", border: "1px solid rgba(217,119,6,0.35)", borderRadius: 10, padding: "3px 10px", fontSize: 9, fontWeight: 600, textTransform: "capitalize" }}>
                  {e.agent_name} · needs human
                </span>
                <span style={{ color: t.textFaint, fontSize: 10 }}>{new Date(e.created_at).toLocaleString()}</span>
              </div>
              <div style={{ color: t.text, fontSize: 12 }}>{e.reasoning}</div>
              {typeof e.details["escalation_reason"] === "string" && (
                <div style={{ color: t.textMuted, fontSize: 11, marginTop: 4 }}>Reason: {String(e.details["escalation_reason"])}</div>
              )}
            </RepCard>
          ))}
        </div>
      )}
    </div>
  );
}