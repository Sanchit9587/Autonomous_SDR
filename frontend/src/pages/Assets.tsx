import { useEffect, useState } from "react";
import { campaignsApi } from "../api/campaigns";
import { assetsApi } from "../api/assets";
import type { AssetType, Campaign, CampaignAsset } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Field, Input, Spinner } from "../components/ui";

const TYPES: AssetType[] = ["image", "pdf", "video", "link", "case_study"];

export function Assets() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [assets, setAssets] = useState<CampaignAsset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [type, setType] = useState<AssetType>("pdf");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");

  useEffect(() => {
    campaignsApi.list().then((cs) => { setCampaigns(cs); if (cs.length) setCampaignId(cs[0].id); })
      .catch((e) => setError(String(e.message))).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!campaignId) return;
    assetsApi.list(campaignId).then(setAssets).catch((e) => setError(String(e.message)));
  }, [campaignId]);

  const create = async () => {
    if (!campaignId || !name || !url) return;
    try {
      await assetsApi.create(campaignId, {
        campaign_id: campaignId, name, asset_type: type, url,
        description: description || undefined, tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setName(""); setUrl(""); setDescription(""); setTags(""); setCreating(false);
      setAssets(await assetsApi.list(campaignId));
    } catch (e) { setError(String((e as Error).message)); }
  };

  if (loading) return <Spinner />;

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: 0 }}>Assets</h1>
        <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)}
          style={{ background: "rgba(255,255,255,0.05)", color: theme.textDim, border: `1px solid ${theme.borderStrong}`, borderRadius: 6, padding: "8px 12px", fontSize: 11, fontFamily: theme.font }}>
          {campaigns.map((c) => <option key={c.id} value={c.id} style={{ background: theme.sidebar }}>{c.name}</option>)}
        </select>
      </div>

      {error && <ErrorText>{error}</ErrorText>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
        {assets.map((a) => (
          <Card key={a.id}>
            <div style={{ fontSize: 18, marginBottom: 8 }}>{iconFor(a.asset_type)}</div>
            <div style={{ color: "#fff", fontSize: 11, fontWeight: 600, marginBottom: 4 }}>{a.name}</div>
            <div style={{ color: theme.textFaint, fontSize: 9, marginBottom: 8, textTransform: "uppercase" }}>{a.asset_type}</div>
            <div style={{ color: theme.textMuted, fontSize: 9, lineHeight: 1.4, minHeight: 26 }}>{a.description ?? ""}</div>
            {a.tags.length > 0 && <div style={{ color: theme.purpleLight, fontSize: 8, marginTop: 6 }}>{a.tags.join(" · ")}</div>}
          </Card>
        ))}
        {assets.length === 0 && <div style={{ color: theme.textMuted, fontSize: 12 }}>No assets for this campaign yet.</div>}
      </div>

      {creating ? (
        <Card>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="Name"><Input value={name} onChange={setName} placeholder="Infra case study" /></Field>
            <Field label="Type">
              <select value={type} onChange={(e) => setType(e.target.value as AssetType)}
                style={{ width: "100%", background: "rgba(255,255,255,0.05)", color: theme.textDim, border: `1px solid ${theme.borderStrong}`, borderRadius: 6, padding: "9px 10px", fontSize: 12, fontFamily: theme.font }}>
                {TYPES.map((t) => <option key={t} value={t} style={{ background: theme.sidebar }}>{t}</option>)}
              </select>
            </Field>
            <div style={{ gridColumn: "span 2" }}><Field label="URL"><Input value={url} onChange={setUrl} placeholder="https://…" /></Field></div>
            <div style={{ gridColumn: "span 2" }}><Field label="Description"><Input value={description} onChange={setDescription} /></Field></div>
            <div style={{ gridColumn: "span 2" }}><Field label="Tags (comma-sep)"><Input value={tags} onChange={setTags} placeholder="infra, technical" /></Field></div>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <Button variant="primary" onClick={create} disabled={!name || !url}>Add Asset</Button>
            <Button onClick={() => setCreating(false)}>Cancel</Button>
          </div>
        </Card>
      ) : (
        <Button variant="primary" onClick={() => setCreating(true)} disabled={!campaignId}>+ New Asset</Button>
      )}
    </div>
  );
}

function iconFor(t: AssetType): string {
  return { image: "🖼", pdf: "📄", video: "🎬", link: "🔗", case_study: "📊" }[t];
}