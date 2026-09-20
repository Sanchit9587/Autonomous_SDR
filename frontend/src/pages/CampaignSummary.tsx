import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { campaignsApi } from "../api/campaigns";
import type { Campaign, FunnelCounts } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Spinner, StatusBadge } from "../components/ui";

export function CampaignSummary() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<Campaign | null>(null);
  const [funnel, setFunnel] = useState<FunnelCounts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([campaignsApi.get(id), campaignsApi.funnel(id)])
      .then(([camp, f]) => { setC(camp); setFunnel(f); })
      .catch((e) => setError(String(e.message)));
  }, [id]);

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!c) return <Spinner />;

  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: 0 }}>{c.name}</h1>
          <StatusBadge status={c.status} />
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Button onClick={() => navigate(`/campaigns/${c.id}/edit`)}>✎ Modify</Button>
          <Button onClick={() => navigate(`/campaigns/${c.id}/prospects`)}>Prospects</Button>
          {c.status === "draft" && <Button variant="primary" onClick={async () => { await campaignsApi.activate(c.id); navigate(0); }}>🚀 Launch</Button>}
        </div>
      </div>

      {c.vision_statement && (
        <div style={{ background: theme.panelGradient, border: `1px solid ${theme.border}`, borderRadius: 10, padding: "18px 22px", marginBottom: 16 }}>
          <div style={{ color: "#fff", fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Vision</div>
          <div style={{ color: "#c9c3d1", fontSize: 12, lineHeight: 1.6 }}>{c.vision_statement}</div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card>
          <SectionHead label="STRATEGY" title="How it acts" color={theme.purpleLight} />
          <Row k="Budget" v={c.budget ? `$${c.budget.toLocaleString()}` : "—"} />
          <Row k="Target scale" v={c.target_scale?.toString() ?? "—"} />
          <Row k="Pace" v={c.pace_per_day ? `${c.pace_per_day}/day` : "—"} />
          <Row k="Duration" v={c.start_date ? `${c.start_date} → ${c.end_date ?? "?"}` : "—"} />
        </Card>

        <Card>
          <SectionHead label="ICP" title="Who we target" color={theme.red} />
          <Row k="Roles" v={c.icp.target_roles.join(", ") || "—"} />
          <Row k="Geography" v={c.icp.geography.join(", ") || "—"} />
          <Row k="Company size" v={c.icp.company_size_min ? `${c.icp.company_size_min}-${c.icp.company_size_max ?? "?"}` : "—"} />
          <Row k="Keywords" v={c.icp.keywords ?? "—"} />
        </Card>

        <Card>
          <SectionHead label="EXECUTION" title="How we reach out" color={theme.green} />
          <Row k="Goals" v={c.goals.join(" · ") || "—"} />
          <Row k="Channels" v={c.channel_policies.filter((p) => p.enabled).map((p) => p.channel).join(" · ") || "—"} />
          <Row k="Modes" v={c.channel_policies.filter((p) => p.enabled).map((p) => `${p.channel}:${p.mode}`).join(", ") || "—"} />
        </Card>

        <Card>
          <SectionHead label="FUNNEL" title="Where prospects are" color={theme.purpleLight} />
          {funnel && Object.entries(funnel).filter(([, n]) => n > 0).map(([stage, n]) => (
            <Row key={stage} k={stage} v={String(n)} />
          ))}
          {funnel && Object.values(funnel).every((n) => n === 0) && (
            <div style={{ color: theme.textMuted, fontSize: 11, paddingTop: 8 }}>No prospects yet.</div>
          )}
        </Card>
      </div>
    </div>
  );
}

function SectionHead({ label, title, color }: { label: string; title: string; color: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ color, fontSize: 9, fontWeight: 700, letterSpacing: 0.5 }}>{label}</div>
      <div style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>{title}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderTop: `1px solid ${theme.border}`, color: theme.textMuted, fontSize: 10 }}>
      <span style={{ textTransform: "capitalize" }}>{k}</span>
      <span style={{ color: "#e5e1ea", fontSize: 11, textAlign: "right" }}>{v}</span>
    </div>
  );
}