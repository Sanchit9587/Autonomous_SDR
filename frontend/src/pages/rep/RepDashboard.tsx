import { useEffect, useState } from "react";
import { repApi, type CampaignOverview } from "../../api/rep";
import type { Campaign, FunnelStage } from "../../types";
import { RepCard, repTheme as t } from "../../components/RepLayout";
import { useIsMobile } from "../../hooks";

const FUNNEL_ORDER: FunnelStage[] = ["discovered", "researched", "qualified", "contacted", "engaged", "meeting", "opportunity"];

export function RepDashboard() {
  const isMobile = useIsMobile();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [overview, setOverview] = useState<CampaignOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    repApi.campaigns().then((cs) => {
      setCampaigns(cs);
      if (cs.length) setSelected(cs[0].id);
    }).catch((e) => setError(String(e.message)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    repApi.overview(selected).then(setOverview).catch((e) => setError(String(e.message)));
  }, [selected]);

  const funnel = overview?.funnel;
  const top = funnel ? Math.max(funnel.discovered || 1, 1) : 1;

  return (
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ color: "#0f4a44", fontSize: 20, fontWeight: 700, margin: 0 }}>
          {overview?.campaign.name ?? "Dashboard"}
        </h1>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}
          style={{ background: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.85)", borderRadius: 14, padding: "6px 12px", fontSize: 11, color: t.text, fontFamily: t.font }}>
          {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {error && <div style={{ color: "#dc2626", fontSize: 12, marginBottom: 12 }}>{error}</div>}
      {campaigns.length === 0 && <RepCard><div style={{ color: t.textMuted, fontSize: 13 }}>No campaigns assigned to you yet.</div></RepCard>}

      {overview && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3, 1fr)", gap: 14, marginBottom: 16 }}>
            <StatCard icon="⚠" label="Escalations" value={String(overview.open_escalations)} tint="rgba(220,38,38,0.15)" />
            <StatCard icon="👥" label="Prospects" value={String(Object.values(overview.funnel).reduce((a, b) => a + b, 0))}
              sub={`${overview.funnel.qualified || 0} qualified · ${overview.funnel.engaged || 0} engaged`} tint="rgba(13,148,136,0.15)" />
            <StatCard icon="📅" label="Meetings" value={String(overview.funnel.meeting || 0)}
              sub={`${overview.funnel.opportunity || 0} opportunities`} tint="rgba(3,105,161,0.15)" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1.3fr 1fr", gap: 14 }}>
            <RepCard>
              <div style={{ color: t.text, fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Prospect funnel</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {FUNNEL_ORDER.map((stage) => {
                  const n = funnel?.[stage] ?? 0;
                  const pct = Math.round((n / top) * 100);
                  return (
                    <div key={stage} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 76, color: t.textMuted, fontSize: 10, textTransform: "capitalize" }}>{stage}</span>
                      <div style={{ flex: 1, background: "rgba(0,0,0,0.05)", borderRadius: 5, overflow: "hidden" }}>
                        <div style={{ width: `${Math.max(pct, n > 0 ? 8 : 0)}%`, background: stage === "meeting" || stage === "opportunity" ? "#16a34a" : stage === "contacted" || stage === "engaged" ? t.primary : "#3b82f6", color: "#fff", fontSize: 10, fontWeight: 600, padding: "6px 8px", boxSizing: "border-box" }}>{n}</div>
                      </div>
                      <span style={{ width: 32, color: t.textFaint, fontSize: 9, textAlign: "right" }}>{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </RepCard>

            <RepCard>
              <div style={{ color: t.text, fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Outcomes</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <Outcome label="Qualified" value={overview.funnel.qualified || 0} color="#16a34a" />
                <Outcome label="Rejected" value={overview.funnel.rejected || 0} color={t.text} />
                <Outcome label="Meetings" value={overview.funnel.meeting || 0} color={t.text} />
                <Outcome label="Opportunities" value={overview.funnel.opportunity || 0} color={t.text} />
              </div>
            </RepCard>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, sub, tint }: { icon: string; label: string; value: string; sub?: string; tint: string }) {
  return (
    <RepCard style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, background: tint, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0 }}>{icon}</div>
      <div>
        <div style={{ color: t.textMuted, fontSize: 9, marginBottom: 4 }}>{label}</div>
        <div style={{ color: t.text, fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{value}</div>
        {sub && <div style={{ color: t.textMuted, fontSize: 9, marginTop: 4 }}>{sub}</div>}
      </div>
    </RepCard>
  );
}

function Outcome({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: "rgba(0,0,0,0.03)", borderRadius: 8, padding: 10 }}>
      <div style={{ color: t.textFaint, fontSize: 8, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color, fontSize: 18, fontWeight: 700, marginTop: 4 }}>{value}</div>
    </div>
  );
}