import { useEffect, useState } from "react";
import { repApi, type ProspectRow } from "../../api/rep";
import type { Campaign } from "../../types";
import { RepCard, repTheme as t } from "../../components/RepLayout";

const stageColor: Record<string, string> = {
  discovered: "#94a3b8", researched: "#475569", qualified: "#1d4ed8", rejected: "#dc2626",
  contacted: "#0d9488", engaged: "#16a34a", meeting: "#16a34a", opportunity: "#7c3aed",
};

export function RepProspects() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selected, setSelected] = useState("");
  const [rows, setRows] = useState<ProspectRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    repApi.campaigns().then((cs) => { setCampaigns(cs); if (cs.length) setSelected(cs[0].id); }).catch((e) => setError(String(e.message)));
  }, []);
  useEffect(() => {
    if (!selected) return;
    repApi.prospects(selected).then(setRows).catch((e) => setError(String(e.message)));
  }, [selected]);

  return (
    <div style={{ maxWidth: 960 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ color: "#0f4a44", fontSize: 20, fontWeight: 700, margin: 0 }}>Prospects</h1>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}
          style={{ background: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.85)", borderRadius: 14, padding: "6px 12px", fontSize: 11, color: t.text }}>
          {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      {error && <div style={{ color: "#dc2626", fontSize: 12, marginBottom: 12 }}>{error}</div>}
      {rows.length === 0 ? (
        <RepCard><div style={{ color: t.textMuted, fontSize: 13 }}>No prospects in this campaign yet.</div></RepCard>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {rows.map(({ link, prospect }) => (
            <RepCard key={link.id}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: t.primary, color: "#fff", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {prospect.profile.name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
                </div>
                <div>
                  <div style={{ color: t.text, fontSize: 13, fontWeight: 700 }}>{prospect.profile.name}</div>
                  <div style={{ color: t.textMuted, fontSize: 10 }}>{prospect.profile.position} · {prospect.profile.company_name}</div>
                </div>
                <span style={{ padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600, background: `${stageColor[link.stage]}22`, color: stageColor[link.stage], border: `1px solid ${stageColor[link.stage]}55`, textTransform: "capitalize" }}>{link.stage}</span>
                <span style={{ flex: 1 }} />
                <div style={{ display: "flex", gap: 16 }}>
                  <Metric label="ICP score" value={link.fit_score != null ? String(link.fit_score) : "—"} />
                  <Metric label="Contacts" value={String(link.contact_count)} />
                </div>
              </div>
              {link.qualification_reasoning && (
                <div style={{ marginTop: 10, color: t.textMuted, fontSize: 11, borderTop: "1px solid rgba(0,0,0,0.06)", paddingTop: 10 }}>{link.qualification_reasoning}</div>
              )}
            </RepCard>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ textAlign: "right" }}>
      <div style={{ color: t.textFaint, fontSize: 8, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: t.text, fontSize: 14, fontWeight: 700 }}>{value}</div>
    </div>
  );
}