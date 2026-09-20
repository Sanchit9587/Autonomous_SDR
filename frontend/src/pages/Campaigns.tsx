import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { campaignsApi } from "../api/campaigns";
import type { Campaign, CampaignStatus } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Spinner, StatusBadge } from "../components/ui";

const NEXT_ACTIONS: Record<CampaignStatus, { label: string; fn: keyof typeof campaignsApi }[]> = {
  draft: [{ label: "Activate", fn: "activate" }],
  live: [{ label: "Pause", fn: "pause" }, { label: "Complete", fn: "complete" }],
  paused: [{ label: "Resume", fn: "resume" }, { label: "Complete", fn: "complete" }],
  completed: [{ label: "Archive", fn: "archive" }],
  archived: [],
};

export function Campaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    campaignsApi
      .list()
      .then(setCampaigns)
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const runAction = async (id: string, fn: keyof typeof campaignsApi) => {
    try {
      // @ts-expect-error dynamic lifecycle call — all take a single id
      await campaignsApi[fn](id);
      load();
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: 0 }}>Campaigns</h1>
        <Button variant="primary" onClick={() => navigate("/campaigns/new")}>+ New Campaign</Button>
      </div>

      {error && <ErrorText>{error}</ErrorText>}
      {loading ? (
        <Spinner />
      ) : campaigns.length === 0 ? (
        <Card><div style={{ color: theme.textMuted, fontSize: 13 }}>No campaigns yet. Create your first one.</div></Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {campaigns.map((c) => (
            <Card key={c.id}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <h2 style={{ color: "#fff", fontSize: 16, fontWeight: 700, margin: 0 }}>{c.name}</h2>
                  <StatusBadge status={c.status} />
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Button onClick={() => navigate(`/campaigns/${c.id}`)}>View</Button>
                  <Button onClick={() => navigate(`/campaigns/${c.id}/edit`)}>✎ Edit</Button>
                  <Button onClick={() => navigate(`/campaigns/${c.id}/prospects`)}>Prospects</Button>
                  {NEXT_ACTIONS[c.status].map((a) => (
                    <Button key={a.label} variant="primary" onClick={() => runAction(c.id, a.fn)}>{a.label}</Button>
                  ))}
                  <Button onClick={() => runAction(c.id, "duplicate")}>Duplicate</Button>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginTop: 14, borderTop: `1px solid ${theme.border}`, paddingTop: 12 }}>
                <Meta label="ICP" value={c.icp.target_roles.join(", ") || "—"} />
                <Meta label="Budget" value={c.budget ? `$${c.budget.toLocaleString()}` : "—"} />
                <Meta label="Pace" value={c.pace_per_day ? `${c.pace_per_day}/day` : "—"} />
                <Meta label="Goals" value={c.goals.join(", ") || "—"} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ color: theme.textFaint, fontSize: 8, textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
      <div style={{ color: theme.textDim, fontSize: 12 }}>{value}</div>
    </div>
  );
}