import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { campaignsApi } from "../api/campaigns";
import { prospectsApi } from "../api/prospects";
import { repApi } from "../api/rep";
import type { AgentDecision, Campaign, CampaignProspectLink, Prospect } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Field, Input, Spinner, StatusBadge } from "../components/ui";

interface Row {
  link: CampaignProspectLink;
  prospect: Prospect;
}

export function Prospects() {
  const { id: campaignId } = useParams();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyLink, setBusyLink] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [discoverBusy, setDiscoverBusy] = useState(false);
  const [discoverResults, setDiscoverResults] = useState<string>("10");
  const fileRef = useRef<HTMLInputElement>(null);

  // add-prospect form
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [company, setCompany] = useState("");
  const [headline, setHeadline] = useState("");
  const [location, setLocation] = useState("");

  // decision modal
  const [historyLink, setHistoryLink] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);

  const load = () => {
    if (!campaignId) return;
    setLoading(true);
    Promise.all([campaignsApi.get(campaignId), repApi.prospects(campaignId)])
      .then(([c, prospectRows]) => {
        setCampaign(c);
        setRows(prospectRows.map((pr) => ({ link: pr.link, prospect: pr.prospect })));
      })
      .catch((e) => setError(String(e.message)))
      .finally(() => setLoading(false));
  };
  useEffect(load, [campaignId]);

  const discoveredCount = rows.filter((r) => r.link.stage === "discovered").length;

  const addProspect = async () => {
    if (!campaignId || !name) return;
    const prospect: Prospect = {
      id: "", created_at: "", updated_at: "",
      profile: {
        name, position: role || null, company_name: company || null, headline: headline || null,
        location: location || null, linkedin_url: null, work_email: null, phone_numbers: [], enrichment_status: "pending",
      },
    };
    try {
      const link = await campaignsApi.addProspect(campaignId, prospect);
      // fetch back the stored prospect id via link.prospect_id — reuse local prospect with that id
      setRows((r) => [...r, { link, prospect: { ...prospect, id: link.prospect_id } }]);
      setName(""); setRole(""); setCompany(""); setHeadline(""); setLocation("");
    } catch (e) { setError(String((e as Error).message)); }
  };

  const uploadCsv = async (file: File) => {
    if (!campaignId) return;
    setError(null); setNotice(null);
    try {
      const r = await prospectsApi.uploadCsv(campaignId, file);
      setNotice(`Imported ${r.added} prospect(s) · ${r.skipped_duplicate} duplicate(s) skipped · ${r.skipped_invalid} invalid row(s).`);
      load();
    } catch (e) { setError(String((e as Error).message)); }
    finally { if (fileRef.current) fileRef.current.value = ""; }
  };

  const researchAllDiscovered = async () => {
    if (!campaignId) return;
    setBatchBusy(true); setError(null); setNotice(null);
    try {
      const r = await prospectsApi.researchDiscovered(campaignId);
      setNotice(`Researched ${r.processed} prospect(s) — ${r.qualified} qualified, ${r.rejected} rejected, ${r.needs_review} need review.`);
      load();
    } catch (e) { setError(String((e as Error).message)); }
    finally { setBatchBusy(false); }
  };

  const discover = async () => {
    if (!campaignId) return;
    setDiscoverBusy(true); setError(null); setNotice(null);
    try {
      const n = Number(discoverResults) || 10;
      const r = await prospectsApi.discover(campaignId, n, 4);
      setNotice(`Found ${r.found} business(es) · ${r.added} added · ${r.skipped_duplicate} duplicate(s) skipped.`);
      load();
    } catch (e) { setError(String((e as Error).message)); }
    finally { setDiscoverBusy(false); }
  };

  const act = async (linkId: string, fn: () => Promise<unknown>, updater?: (l: CampaignProspectLink) => void) => {
    setBusyLink(linkId);
    setError(null);
    try {
      await fn();
      if (campaignId && updater) {
        // Reload the link to reflect stage/score changes.
        const fresh = await campaignsApi.funnel(campaignId); // touch to ensure campaign live
        void fresh;
      }
    } catch (e) { setError(String((e as Error).message)); }
    finally { setBusyLink(null); }
  };

  const runResearch = (row: Row) =>
    act(row.link.id, async () => {
      const res = await prospectsApi.research(campaignId!, row.link.id);
      setRows((rs) => rs.map((r) => (r.link.id === row.link.id ? { ...r, link: res.link } : r)));
    });

  const runPersonalize = (row: Row) =>
    act(row.link.id, async () => {
      const res = await prospectsApi.personalize(campaignId!, row.link.id);
      alert(`Draft (${res.decision.details["draft_method"]}) via ${res.decision.details["channel"]}:\n\n${res.decision.details["draft_message"]}`);
    });

  const simulateReply = (row: Row) =>
    act(row.link.id, async () => {
      const msg = prompt("Simulate an inbound reply from this prospect:", "This sounds interesting, tell me more!");
      if (!msg) return;
      // Move to contacted first if needed so converse transitions are valid.
      if (row.link.stage === "qualified") {
        await prospectsApi.transition(campaignId!, row.link.id, "contacted");
      }
      const res = await prospectsApi.converse(campaignId!, row.link.id, msg);
      alert(`Converse verdict: ${res.decision.verdict}\n${res.decision.reasoning}`);
      setRows((rs) => rs.map((r) => (r.link.id === row.link.id ? { ...r, link: { ...r.link, stage: (res.decision.details["target_stage"] as CampaignProspectLink["stage"]) ?? r.link.stage } } : r)));
    });

  const setDealValue = (row: Row) =>
    act(row.link.id, async () => {
      const raw = prompt(`Deal value for ${row.prospect.profile.name} (USD):`, row.link.deal_value != null ? String(row.link.deal_value) : "");
      if (raw == null || raw.trim() === "") return;
      const value = Number(raw);
      if (Number.isNaN(value)) { setError("Deal value must be a number."); return; }
      const updated = await prospectsApi.setDealValue(campaignId!, row.link.id, value);
      setRows((rs) => rs.map((r) => (r.link.id === row.link.id ? { ...r, link: updated } : r)));
    });

  const openHistory = async (row: Row) => {
    setHistoryLink(row.link.id);
    try {
      setDecisions(await prospectsApi.decisions(campaignId!, row.link.id));
    } catch (e) { setError(String((e as Error).message)); }
  };

  if (loading) return <Spinner />;

  return (
    <div style={{ maxWidth: 1100 }}>
      <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: "0 0 6px 0" }}>Prospects</h1>
      <div style={{ color: theme.textMuted, fontSize: 12, marginBottom: 18 }}>{campaign?.name} · {campaign?.status}</div>

      {error && <ErrorText>{error}</ErrorText>}
      {notice && (
        <div style={{ color: theme.green, fontSize: 12, background: "rgba(74,222,128,0.1)", border: `1px solid rgba(74,222,128,0.3)`, borderRadius: 8, padding: "8px 12px", marginBottom: 14 }}>
          {notice}
        </div>
      )}

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>Import & research</div>
            <div style={{ color: theme.textMuted, fontSize: 10, marginTop: 2 }}>
              Upload a CSV of leads, or discover new companies from this campaign's ICP, then research all discovered prospects at once.
            </div>
          </div>
          <span style={{ flex: 1 }} />
          <input ref={fileRef} type="file" accept=".csv" style={{ display: "none" }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCsv(f); }} />
          <Button onClick={() => fileRef.current?.click()}>⬆ Upload CSV</Button>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Input value={discoverResults} onChange={setDiscoverResults} style={{ width: 48, textAlign: "center" }} />
            <Button onClick={discover} disabled={discoverBusy}>{discoverBusy ? "Discovering…" : "🔎 Discover via search"}</Button>
          </span>
          <Button variant="primary" onClick={researchAllDiscovered} disabled={batchBusy || discoveredCount === 0}>
            {batchBusy ? "Researching…" : `🔬 Research all discovered${discoveredCount ? ` (${discoveredCount})` : ""}`}
          </Button>
        </div>
        <div style={{ color: theme.textFaint, fontSize: 9, marginTop: 10 }}>
          CSV headers are flexible — e.g. name/full name, company, title/role, email, linkedin, location, employees. Only name is required.
          Discovery builds a search from this campaign's ICP (industry/criteria + geography) and returns company-level leads — only available when the backend is running locally, not on the deployed Vercel instance.
        </div>
      </Card>

      <Card style={{ marginBottom: 20 }}>
        <div style={{ color: "#fff", fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Add prospect</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
          <Field label="Name"><Input value={name} onChange={setName} /></Field>
          <Field label="Role"><Input value={role} onChange={setRole} placeholder="CTO" /></Field>
          <Field label="Company"><Input value={company} onChange={setCompany} /></Field>
          <Field label="Headline"><Input value={headline} onChange={setHeadline} /></Field>
          <Field label="Location"><Input value={location} onChange={setLocation} /></Field>
        </div>
        <div style={{ marginTop: 12 }}><Button variant="primary" onClick={addProspect} disabled={!name}>Add</Button></div>
      </Card>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {rows.length === 0 && <div style={{ color: theme.textMuted, fontSize: 12 }}>Add a prospect above, then run Research on it.</div>}
        {rows.map((row) => (
          <Card key={row.link.id}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div style={{ width: 34, height: 34, borderRadius: 8, background: theme.purple, color: "#fff", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {row.prospect.profile.name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
              </div>
              <div>
                <div style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>{row.prospect.profile.name}</div>
                <div style={{ color: theme.textMuted, fontSize: 10 }}>{row.prospect.profile.position} · {row.prospect.profile.company_name}</div>
              </div>
              <StatusBadge status={row.link.stage} />
              {row.link.fit_score != null && (
                <span style={{ color: theme.textDim, fontSize: 11 }}>ICP {row.link.fit_score}</span>
              )}
              {row.link.stage === "opportunity" && (
                <span style={{ color: theme.green, fontSize: 11 }}>
                  {row.link.deal_value != null ? `$${row.link.deal_value.toFixed(2)}` : "no deal value yet"}
                </span>
              )}
              <span style={{ flex: 1 }} />
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Button onClick={() => runResearch(row)} disabled={busyLink === row.link.id}>🔬 Research</Button>
                <Button onClick={() => runPersonalize(row)} disabled={busyLink === row.link.id || row.link.stage !== "qualified"}>✍ Personalize</Button>
                <Button onClick={() => simulateReply(row)} disabled={busyLink === row.link.id}>💬 Sim. reply</Button>
                {row.link.stage === "opportunity" && (
                  <Button onClick={() => setDealValue(row)} disabled={busyLink === row.link.id}>💰 Deal value</Button>
                )}
                <Button onClick={() => openHistory(row)}>↺ History</Button>
              </div>
            </div>
            {row.link.qualification_reasoning && (
              <div style={{ marginTop: 10, color: theme.textMuted, fontSize: 11, borderTop: `1px solid ${theme.border}`, paddingTop: 10 }}>
                {row.link.qualification_reasoning}
              </div>
            )}
          </Card>
        ))}
      </div>

      {historyLink && (
        <div onClick={() => setHistoryLink(null)} style={{ position: "fixed", inset: 0, background: "rgba(10,6,16,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 24 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: theme.sidebar, border: `1px solid ${theme.borderStrong}`, borderRadius: 12, padding: 24, maxWidth: 640, width: "100%", maxHeight: "85vh", overflowY: "auto", position: "relative" }}>
            <span onClick={() => setHistoryLink(null)} style={{ position: "absolute", top: 14, right: 16, color: theme.textMuted, cursor: "pointer" }}>✕</span>
            <div style={{ color: "#fff", fontSize: 15, fontWeight: 700, marginBottom: 16 }}>Decision history</div>
            {decisions.length === 0 && <div style={{ color: theme.textMuted, fontSize: 12 }}>No decisions recorded yet.</div>}
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {decisions.map((d) => (
                <div key={d.id} style={{ borderLeft: `2px solid ${theme.purple}`, paddingLeft: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ color: theme.purpleLight, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>{d.agent_name} · {d.verdict}</span>
                    <span style={{ color: theme.textFaint, fontSize: 10 }}>{new Date(d.created_at).toLocaleString()}</span>
                  </div>
                  <div style={{ color: theme.textDim, fontSize: 12 }}>{d.reasoning}</div>
                  {Object.keys(d.details).length > 0 && (
                    <pre style={{ color: theme.textFaint, fontSize: 10, marginTop: 6, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      {JSON.stringify(d.details, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>              
      )}
    </div>
  );
}                                                                                                                     