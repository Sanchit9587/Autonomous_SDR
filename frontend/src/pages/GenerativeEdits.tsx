import { useEffect, useState } from "react";
import { campaignsApi } from "../api/campaigns";
import { prospectsApi } from "../api/prospects";
import { generativeEditsApi, type GenerativeEdits, type Suggestion } from "../api/generativeEdits";
import type { Campaign } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Spinner, StatusBadge } from "../components/ui";

interface CampaignEdits {
  campaign: Campaign;
  edits: GenerativeEdits | null;
  loading: boolean;
  reviewing: boolean;
  discarded: boolean;
  applyingId: string | null;   // suggestion id currently being applied, or "*" for apply-all
  notice: string | null;
}

export function GenerativeEditsPage() {
  const [rows, setRows] = useState<CampaignEdits[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingAll, setLoadingAll] = useState(true);

  const fetchOne = async (campaign: Campaign): Promise<CampaignEdits> => {
    try {
      const edits = await generativeEditsApi.get(campaign.id);
      return { campaign, edits, loading: false, reviewing: false, discarded: false, applyingId: null, notice: null };
    } catch (e) {
      return { campaign, edits: null, loading: false, reviewing: false, discarded: false, applyingId: null, notice: String((e as Error).message) };
    }
  };

  const loadAll = async () => {
    setLoadingAll(true);
    setError(null);
    try {
      const campaigns = await campaignsApi.list();
      const results = await Promise.all(campaigns.map(fetchOne));
      setRows(results);
    } catch (e) { setError(String((e as Error).message)); }
    finally { setLoadingAll(false); }
  };

  useEffect(() => { loadAll(); }, []);

  const regenerateOne = async (campaignId: string) => {
    setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, loading: true } : r)));
    const target = rows.find((r) => r.campaign.id === campaignId);
    if (!target) return;
    const fresh = await fetchOne(target.campaign);
    setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? fresh : r)));
  };

  const toggleReview = (campaignId: string) => {
    setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, reviewing: !r.reviewing } : r)));
  };

  const discard = (campaignId: string) => {
    setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, discarded: true, reviewing: false } : r)));
  };

  // A suggestion is just a pointer to an existing endpoint + payload — applying
  // it means calling that same endpoint a human would, nothing more.
  const applySuggestion = async (campaignId: string, s: Suggestion) => {
    if (s.kind === "action" && s.action === "research_discovered") {
      await prospectsApi.researchDiscovered(campaignId);
    } else if (s.kind === "config_diff" && s.diff) {
      await campaignsApi.update(campaignId, s.diff);
    }
  };

  const applyOne = async (campaignId: string, s: Suggestion) => {
    setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, applyingId: s.id, notice: null } : r)));
    try {
      await applySuggestion(campaignId, s);
      await regenerateOne(campaignId);
      setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, notice: `Applied: ${s.title}` } : r)));
    } catch (e) {
      setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, notice: String((e as Error).message) } : r)));
    } finally {
      setRows((rs) => rs.map((r) => (r.campaign.id === campaignId ? { ...r, applyingId: null } : r)));
    }
  };

  const applyAll = async (row: CampaignEdits) => {
    if (!row.edits) return;
    setRows((rs) => rs.map((r) => (r.campaign.id === row.campaign.id ? { ...r, applyingId: "*", notice: null } : r)));
    try {
      for (const s of row.edits.suggestions) {
        await applySuggestion(row.campaign.id, s);
      }
      await regenerateOne(row.campaign.id);
      setRows((rs) => rs.map((r) => (r.campaign.id === row.campaign.id ? { ...r, notice: `Applied ${row.edits!.suggestions.length} suggestion(s).` } : r)));
    } catch (e) {
      setRows((rs) => rs.map((r) => (r.campaign.id === row.campaign.id ? { ...r, notice: String((e as Error).message) } : r)));
    } finally {
      setRows((rs) => rs.map((r) => (r.campaign.id === row.campaign.id ? { ...r, applyingId: null } : r)));
    }
  };

  return (
    <div style={{ maxWidth: 1100 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 20 }}>
        <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: 0 }}>Generative Edits</h1>
        <Button variant="primary" onClick={loadAll} disabled={loadingAll}>{loadingAll ? "Regenerating…" : "↻ Regenerate all"}</Button>
      </div>

      {error && <ErrorText>{error}</ErrorText>}
      {loadingAll && rows.length === 0 && <Spinner />}
      {!loadingAll && rows.length === 0 && !error && (
        <Card><div style={{ color: theme.textMuted, fontSize: 13 }}>No campaigns yet.</div></Card>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {rows.map((row) => (
          <CampaignEditsCard
            key={row.campaign.id}
            row={row}
            onRegenerate={() => regenerateOne(row.campaign.id)}
            onToggleReview={() => toggleReview(row.campaign.id)}
            onDiscard={() => discard(row.campaign.id)}
            onApplyOne={(s) => applyOne(row.campaign.id, s)}
            onApplyAll={() => applyAll(row)}
          />
        ))}
      </div>
    </div>
  );
}

function CampaignEditsCard({
  row, onRegenerate, onToggleReview, onDiscard, onApplyOne, onApplyAll,
}: {
  row: CampaignEdits;
  onRegenerate: () => void;
  onToggleReview: () => void;
  onDiscard: () => void;
  onApplyOne: (s: Suggestion) => void;
  onApplyAll: () => void;
}) {
  const { campaign, edits, loading, reviewing, discarded, applyingId, notice } = row;

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ color: "#fff", fontSize: 16, fontWeight: 700, margin: 0 }}>{campaign.name}</h2>
          <StatusBadge status={campaign.status} />
        </div>
        <Button onClick={onRegenerate} disabled={loading}>{loading ? "…" : "↻ Regenerate"}</Button>
      </div>

      {loading ? (
        <Spinner />
      ) : !edits ? (
        <ErrorText>{notice ?? "Could not load generative edits for this campaign."}</ErrorText>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 16, marginBottom: 18 }}>
            <Tile label="Conversions" value={String(edits.conversions)} sub="reached Opportunity" />
            <Tile label="Best channel" value={edits.best_channel ? edits.best_channel[0].toUpperCase() + edits.best_channel.slice(1) : "—"}
              sub={edits.best_channel_reply_rate != null ? `${(edits.best_channel_reply_rate * 100).toFixed(0)}% reply rate` : "not enough volume yet"} />
            <Tile label="Escalations" value={String(edits.open_escalations)} sub="open now" />
            <Tile label="Stuck at Discovered" value={String(edits.stale_discovered)} sub="never researched" />
          </div>

          {notice && (
            <div style={{ color: theme.green, fontSize: 11, marginBottom: 12 }}>{notice}</div>
          )}

          {!discarded && edits.suggestions.length > 0 && (
            <div style={{ background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.35)", borderRadius: 10, padding: "14px 18px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <span style={{ width: 34, height: 34, background: "rgba(139,92,246,0.25)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: theme.purpleLighter, fontSize: 16, flexShrink: 0 }}>✨</span>
                  <div>
                    <div style={{ color: "#fff", fontSize: 12, fontWeight: 700 }}>{edits.suggestions.length} generative suggestion{edits.suggestions.length === 1 ? "" : "s"} ready</div>
                    <div style={{ color: theme.textMuted, fontSize: 10, marginTop: 2 }}>{edits.suggestions.map((s) => s.title).join(" · ")}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  <Button onClick={onToggleReview}>👁 {reviewing ? "Hide" : "Review"}</Button>
                  <Button onClick={onApplyAll} disabled={applyingId != null}
                    style={{ background: "rgba(74,222,128,0.15)", color: theme.green, border: "1px solid rgba(74,222,128,0.4)" }}>
                    {applyingId === "*" ? "Applying…" : "✓ Apply all"}
                  </Button>
                  <Button onClick={onDiscard} disabled={applyingId != null}>✕ Discard</Button>
                </div>
              </div>

              {reviewing && (
                <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10, borderTop: `1px solid ${theme.border}`, paddingTop: 14 }}>
                  {edits.suggestions.map((s) => (
                    <div key={s.id} style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, background: "rgba(20,14,28,0.5)", borderRadius: 8, padding: "10px 14px" }}>
                      <div>
                        <div style={{ color: "#fff", fontSize: 11, fontWeight: 700 }}>{s.title}</div>
                        <div style={{ color: theme.textMuted, fontSize: 10, marginTop: 4, lineHeight: 1.5 }}>{s.reasoning}</div>
                      </div>
                      <Button onClick={() => onApplyOne(s)} disabled={applyingId != null} style={{ flexShrink: 0 }}>
                        {applyingId === s.id ? "…" : "Apply"}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {(discarded || edits.suggestions.length === 0) && (
            <div style={{ color: theme.textFaint, fontSize: 11 }}>
              {discarded ? "Suggestions discarded — hit Regenerate to see them again." : "No suggestions right now — this campaign looks healthy by the signals we track."}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <div style={{ color: theme.textMuted, fontSize: 10, marginBottom: 6 }}>{label}</div>
      <div style={{ color: "#fff", fontSize: 22, fontWeight: 700 }}>{value}</div>
      <div style={{ color: theme.textFaint, fontSize: 9, marginTop: 4, lineHeight: 1.4 }}>{sub}</div>
    </div>
  );
}