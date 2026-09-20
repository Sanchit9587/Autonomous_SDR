import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { repApi, type CampaignOverview } from "../api/rep";
import type { Campaign, FunnelStage } from "../types";
import { Card, Button } from "../components/ui";
import { theme } from "../theme";

const FUNNEL_ORDER: FunnelStage[] = ["discovered", "researched", "qualified", "contacted", "engaged", "meeting", "opportunity"];

// Same underlying data Mark's rep dashboard uses (repApi -> /rep/campaigns,
// /rep/campaigns/{id}/overview) — a manager sees every campaign there (see
// _visible_to() in rep_api.py), so no separate manager-only endpoint is
// needed. Funnel counts and escalation counts are computed straight from the
// DB, not mocked.
export function Dashboard() {
  const navigate = useNavigate();
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
    <div style={{ maxWidth: 1000 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: 0 }}>
          {overview?.campaign.name ?? "Dashboard"}
        </h1>
        {campaigns.length > 0 && (
          <select value={selected} onChange={(e) => setSelected(e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", border: `1px solid ${theme.borderStrong}`, borderRadius: 14, padding: "6px 12px", fontSize: 11, color: theme.textDim, fontFamily: theme.font }}>
            {campaigns.map((c) => <option key={c.id} value={c.id} style={{ background: theme.sidebar }}>{c.name} · {c.status}</option>)}
          </select>
        )}
      </div>

      {error && <div style={{ color: theme.red, fontSize: 12, marginBottom: 12 }}>{error}</div>}

      {campaigns.length === 0 && !error && (
        <Card>
          <div style={{ color: theme.textMuted, fontSize: 13, marginBottom: 12 }}>No campaigns yet — create one to get started.</div>
          <Button variant="primary" onClick={() => navigate("/campaigns/new")}>+ New campaign</Button>
        </Card>
      )}

      {overview && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 16 }}>
            <StatCard icon="⚠" label="Escalations" value={String(overview.open_escalations)} tint="rgba(242,139,150,0.18)" />
            <StatCard icon="👥" label="Prospects" value={String(Object.values(overview.funnel).reduce((a, b) => a + b, 0))}
              sub={`${overview.funnel.qualified || 0} qualified · ${overview.funnel.engaged || 0} engaged`} tint="rgba(139,92,246,0.18)" />
            <StatCard icon="📅" label="Meetings" value={String(overview.funnel.meeting || 0)}
              sub={`${overview.funnel.opportunity || 0} opportunities`} tint="rgba(74,222,128,0.18)" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 16 }}>
            <StatCard icon="💵" label="Spend so far" value={`$${overview.total_spend.toFixed(2)}`}
              sub="cost-per-mille × touches sent" tint="rgba(96,140,255,0.18)" />
            <StatCard icon="🎯" label="CAC" value={overview.cac != null ? `$${overview.cac.toFixed(2)}` : "—"}
              sub={overview.cac != null ? `over ${overview.opportunities} opportunit${overview.opportunities === 1 ? "y" : "ies"}` : "no opportunities yet"} tint="rgba(230,170,60,0.18)" />
            <StatCard icon="💰" label="Avg. deal value" value={overview.avg_deal_value != null ? `$${overview.avg_deal_value.toFixed(2)}` : "—"}
              sub={overview.deals_with_value > 0 ? `${overview.deals_with_value} deal(s) entered` : "none entered yet"} tint="rgba(74,222,128,0.18)" />
            <StatCard icon="📈" label="LTV : CAC" value={overview.ltv_cac_ratio != null ? `${overview.ltv_cac_ratio.toFixed(1)}×` : "—"}
              sub="enter deal values on Prospects" tint="rgba(139,92,246,0.18)" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 14 }}>
            <Card>
              <div style={{ color: "#fff", fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Prospect funnel</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {FUNNEL_ORDER.map((stage) => {
                  const n = funnel?.[stage] ?? 0;
                  const pct = Math.round((n / top) * 100);
                  return (
                    <div key={stage} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 76, color: theme.textMuted, fontSize: 10, textTransform: "capitalize" }}>{stage}</span>
                      <div style={{ flex: 1, background: "rgba(255,255,255,0.05)", borderRadius: 5, overflow: "hidden" }}>
                        <div style={{
                          width: `${Math.max(pct, n > 0 ? 8 : 0)}%`,
                          background: stage === "meeting" || stage === "opportunity" ? theme.green : stage === "contacted" || stage === "engaged" ? theme.purple : "#6a8fd8",
                          color: "#fff", fontSize: 10, fontWeight: 600, padding: "6px 8px", boxSizing: "border-box",
                        }}>{n}</div>
                      </div>
                      <span style={{ width: 32, color: theme.textFaint, fontSize: 9, textAlign: "right" }}>{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card>
              <div style={{ color: "#fff", fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Outcomes</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <Outcome label="Qualified" value={overview.funnel.qualified || 0} color={theme.green} />
                <Outcome label="Rejected" value={overview.funnel.rejected || 0} color={theme.textDim} />
                <Outcome label="Meetings" value={overview.funnel.meeting || 0} color={theme.textDim} />
                <Outcome label="Opportunities" value={overview.funnel.opportunity || 0} color={theme.textDim} />
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, sub, tint }: { icon: string; label: string; value: string; sub?: string; tint: string }) {
  return (
    <Card style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, background: tint, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0 }}>{icon}</div>
      <div>
        <div style={{ color: theme.textMuted, fontSize: 9, marginBottom: 4 }}>{label}</div>
        <div style={{ color: "#fff", fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{value}</div>
        {sub && <div style={{ color: theme.textMuted, fontSize: 9, marginTop: 4 }}>{sub}</div>}
      </div>
    </Card>
  );
}

function Outcome({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: 10 }}>
      <div style={{ color: theme.textFaint, fontSize: 8, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color, fontSize: 18, fontWeight: 700, marginTop: 4 }}>{value}</div>
    </div>
  );
}