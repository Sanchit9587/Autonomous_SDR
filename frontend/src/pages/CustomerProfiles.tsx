import { useEffect, useState } from "react";
import { campaignsApi } from "../api/campaigns";
import { personasApi } from "../api/personas";
import type { Campaign, Persona, Tone } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Field, Input, Spinner } from "../components/ui";

const TONES: Tone[] = ["professional", "casual", "consultative", "direct", "friendly", "executive"];

export function CustomerProfiles() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState<string>("");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [tone, setTone] = useState<Tone>("professional");
  const [importance, setImportance] = useState("1");

  useEffect(() => {
    campaignsApi.list().then((cs) => {
      setCampaigns(cs);
      if (cs.length) setCampaignId(cs[0].id);
    }).catch((e) => setError(String(e.message))).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!campaignId) return;
    personasApi.list(campaignId).then(setPersonas).catch((e) => setError(String(e.message)));
  }, [campaignId]);

  const create = async () => {
    if (!campaignId || !name) return;
    try {
      await personasApi.create(campaignId, {
        campaign_id: campaignId, name, qualification_notes: notes || undefined,
        tone, importance: Number(importance) || 1,
      });
      setName(""); setNotes(""); setImportance("1"); setTone("professional"); setCreating(false);
      setPersonas(await personasApi.list(campaignId));
    } catch (e) { setError(String((e as Error).message)); }
  };

  if (loading) return <Spinner />;

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: 0 }}>Customer Profiles</h1>
        <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)}
          style={{ background: "rgba(255,255,255,0.05)", color: theme.textDim, border: `1px solid ${theme.borderStrong}`, borderRadius: 6, padding: "8px 12px", fontSize: 11, fontFamily: theme.font }}>
          {campaigns.map((c) => <option key={c.id} value={c.id} style={{ background: theme.sidebar }}>{c.name}</option>)}
        </select>
      </div>

      {error && <ErrorText>{error}</ErrorText>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 20 }}>
        {personas.map((p) => (
          <Card key={p.id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>{p.name}</div>
              <span style={{ color: theme.purpleLighter, fontSize: 9, border: `1px solid ${theme.borderStrong}`, borderRadius: 10, padding: "2px 8px" }}>
                ★ {p.importance}
              </span>
            </div>
            <div style={{ color: theme.textMuted, fontSize: 10, lineHeight: 1.5, marginBottom: 10, minHeight: 30 }}>{p.qualification_notes ?? "—"}</div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: theme.textFaint }}>
              <span>Tone: <span style={{ color: theme.textDim, textTransform: "capitalize" }}>{p.tone}</span></span>
              <span>{Object.keys(p.templates).length} templates</span>
            </div>
          </Card>
        ))}
        {personas.length === 0 && <div style={{ color: theme.textMuted, fontSize: 12 }}>No profiles for this campaign yet.</div>}
      </div>

      {creating ? (
        <Card>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="Name"><Input value={name} onChange={setName} placeholder="Technical Founder" /></Field>
            <Field label="Importance (1 = normal)"><Input value={importance} onChange={setImportance} type="number" /></Field>
            <div style={{ gridColumn: "span 2" }}>
              <Field label="Qualification Notes (used by Research RAG)">
                <Input value={notes} onChange={setNotes} placeholder="hands-on technical founder, infra & platform engineering" />
              </Field>
            </div>
            <Field label="Tone">
              <select value={tone} onChange={(e) => setTone(e.target.value as Tone)}
                style={{ width: "100%", background: "rgba(255,255,255,0.05)", color: theme.textDim, border: `1px solid ${theme.borderStrong}`, borderRadius: 6, padding: "9px 10px", fontSize: 12, fontFamily: theme.font }}>
                {TONES.map((t) => <option key={t} value={t} style={{ background: theme.sidebar }}>{t}</option>)}
              </select>
            </Field>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <Button variant="primary" onClick={create} disabled={!name}>Create Profile</Button>
            <Button onClick={() => setCreating(false)}>Cancel</Button>
          </div>
        </Card>
      ) : (
        <Button variant="primary" onClick={() => setCreating(true)} disabled={!campaignId}>+ New Profile</Button>
      )}
    </div>
  );
}