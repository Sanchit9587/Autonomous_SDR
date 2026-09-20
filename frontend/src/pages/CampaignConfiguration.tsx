import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { campaignsApi, type CreateCampaignBody } from "../api/campaigns";
import { usersApi } from "../api/users";
import type { Channel, ChannelMode, ChannelPolicy, User } from "../types";
import { theme } from "../theme";
import { Button, Card, ErrorText, Field, Input } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const CHANNELS: Channel[] = ["email", "linkedin", "sms", "voice"];
const MODES: ChannelMode[] = ["automate", "approval", "manual"];
const GOALS = ["book_meeting", "sale", "signup", "free_trial"];

export function CampaignConfiguration({ mode }: { mode: "create" | "edit" }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [name, setName] = useState("");
  const [vision, setVision] = useState("");
  const [roles, setRoles] = useState("");
  const [geo, setGeo] = useState("");
  const [keywords, setKeywords] = useState("");
  const [sizeMin, setSizeMin] = useState("");
  const [sizeMax, setSizeMax] = useState("");
  const [budget, setBudget] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [targetScale, setTargetScale] = useState("");
  const [pace, setPace] = useState("");
  const [goals, setGoals] = useState<string[]>([]);
  const [threshold, setThreshold] = useState("70");
  const [policies, setPolicies] = useState<ChannelPolicy[]>(
    CHANNELS.map((c) => ({ channel: c, enabled: c === "email" || c === "linkedin", mode: "approval", cpm: null, daily_limit: null, working_hours: null }))
  );
  const [assignedRepIds, setAssignedRepIds] = useState<string[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Load all users so the manager can pick team members to assign.
  useEffect(() => {
    usersApi.list().then(setAllUsers).catch(() => { /* non-fatal: picker just stays empty */ });
  }, []);

  useEffect(() => {
    if (mode === "edit" && id) {
      campaignsApi.get(id).then((c) => {
        setName(c.name);
        setVision(c.vision_statement ?? "");
        setRoles(c.icp.target_roles.join(", "));
        setGeo(c.icp.geography.join(", "));
        setKeywords(c.icp.keywords ?? "");
        setSizeMin(c.icp.company_size_min?.toString() ?? "");
        setSizeMax(c.icp.company_size_max?.toString() ?? "");
        setBudget(c.budget?.toString() ?? "");
        setStartDate(c.start_date ?? "");
        setEndDate(c.end_date ?? "");
        setTargetScale(c.target_scale?.toString() ?? "");
        setPace(c.pace_per_day?.toString() ?? "");
        setGoals(c.goals);
        setThreshold(c.agent_settings?.research?.decision_threshold?.toString() ?? "70");
        if (c.channel_policies.length) setPolicies(c.channel_policies);
        setAssignedRepIds(c.assigned_rep_ids ?? []);
      }).catch((e) => setError(String(e.message)));
    }
  }, [mode, id]);

  const num = (s: string) => (s.trim() === "" ? undefined : Number(s));
  const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const buildBody = (): CreateCampaignBody => ({
    name,
    owner: user?.id ?? "unknown",
    vision_statement: vision || undefined,
    icp: {
      target_roles: list(roles),
      geography: list(geo),
      keywords: keywords || undefined,
      company_size_min: num(sizeMin),
      company_size_max: num(sizeMax),
    },
    budget: num(budget),
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    target_scale: num(targetScale),
    pace_per_day: num(pace),
    goals,
    channel_policies: policies,
    default_channel_priority: policies.filter((p) => p.enabled).map((p) => p.channel),
    agent_settings: { research: { enabled: true, decision_threshold: num(threshold) ?? 70, tools_allowed: [] } },
    assigned_rep_ids: assignedRepIds,
  });

  const save = async () => {
    setError(null);
    setBusy(true);
    try {
      if (mode === "create") {
        const c = await campaignsApi.create(buildBody());
        navigate(`/campaigns/${c.id}`);
      } else if (id) {
        await campaignsApi.update(id, buildBody());
        navigate(`/campaigns/${id}`);
      }
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const updatePolicy = (channel: Channel, patch: Partial<ChannelPolicy>) =>
    setPolicies((prev) => prev.map((p) => (p.channel === channel ? { ...p, ...patch } : p)));

  return (
    <div style={{ maxWidth: 900 }}>
      <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 700, margin: "0 0 20px 0" }}>
        {mode === "create" ? "New Campaign" : "Edit Campaign"}
      </h1>
      {error && <ErrorText>{error}</ErrorText>}

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Field label="Campaign Name"><Input value={name} onChange={setName} placeholder="US SaaS CTO Outreach" /></Field>
          <Field label="Vision Statement">
            <textarea value={vision} onChange={(e) => setVision(e.target.value)} rows={3}
              style={{ width: "100%", padding: "9px 10px", borderRadius: 6, background: "rgba(255,255,255,0.05)", border: `1px solid ${theme.borderStrong}`, color: theme.text, fontSize: 12, fontFamily: theme.font, boxSizing: "border-box", resize: "vertical" }} />
          </Field>
        </div>
      </Card>

      <SectionTitle>Ideal Customer Profile</SectionTitle>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Target Roles (comma-sep)"><Input value={roles} onChange={setRoles} placeholder="CTO, VP Engineering" /></Field>
          <Field label="Geography (comma-sep)"><Input value={geo} onChange={setGeo} placeholder="United States" /></Field>
          <Field label="Keywords"><Input value={keywords} onChange={setKeywords} placeholder="SaaS" /></Field>
          <Field label="Qualify Threshold (0-100)"><Input value={threshold} onChange={setThreshold} type="number" /></Field>
          <Field label="Company Size Min"><Input value={sizeMin} onChange={setSizeMin} type="number" placeholder="50" /></Field>
          <Field label="Company Size Max"><Input value={sizeMax} onChange={setSizeMax} type="number" placeholder="500" /></Field>
        </div>
      </Card>

      <SectionTitle>Strategy</SectionTitle>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
          <Field label="Budget ($)"><Input value={budget} onChange={setBudget} type="number" /></Field>
          <Field label="Start Date"><Input value={startDate} onChange={setStartDate} type="date" /></Field>
          <Field label="End Date"><Input value={endDate} onChange={setEndDate} type="date" /></Field>
          <Field label="Target Scale"><Input value={targetScale} onChange={setTargetScale} type="number" /></Field>
          <Field label="Pace (touches/day)"><Input value={pace} onChange={setPace} type="number" /></Field>
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ color: theme.textMuted, fontSize: 9, marginBottom: 8 }}>GOALS</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {GOALS.map((g) => {
              const on = goals.includes(g);
              return (
                <span key={g} onClick={() => setGoals((prev) => (on ? prev.filter((x) => x !== g) : [...prev, g]))}
                  style={{ cursor: "pointer", fontSize: 10, padding: "5px 12px", borderRadius: 14,
                    background: on ? "rgba(120,80,220,0.3)" : "rgba(255,255,255,0.05)",
                    border: `1px solid ${on ? "rgba(150,100,240,0.4)" : theme.borderStrong}`,
                    color: on ? "#e0d8f0" : theme.textMuted }}>
                  {on ? "✓ " : ""}{g.replace("_", " ")}
                </span>
              );
            })}
          </div>
        </div>
      </Card>

      <SectionTitle>Channels & Permissions</SectionTitle>
      <Card style={{ marginBottom: 16 }}>
        {policies.map((p) => (
          <div key={p.channel} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: `1px solid ${theme.border}`, flexWrap: "wrap" }}>
            <span style={{ width: 80, color: theme.textDim, fontSize: 11, textTransform: "capitalize" }}>{p.channel}</span>
            <label style={{ display: "flex", alignItems: "center", gap: 5, color: theme.textMuted, fontSize: 10 }}>
              <input type="checkbox" checked={p.enabled} onChange={(e) => updatePolicy(p.channel, { enabled: e.target.checked })} /> on
            </label>
            <select value={p.mode} onChange={(e) => updatePolicy(p.channel, { mode: e.target.value as ChannelMode })}
              style={{ background: "rgba(255,255,255,0.05)", color: theme.textDim, border: `1px solid ${theme.borderStrong}`, borderRadius: 5, padding: "4px 8px", fontSize: 10, fontFamily: theme.font }}>
              {MODES.map((m) => <option key={m} value={m} style={{ background: theme.sidebar }}>{m}</option>)}
            </select>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ color: theme.textFaint, fontSize: 9 }}>limit/day</span>
              <input type="number" value={p.daily_limit ?? ""} onChange={(e) => updatePolicy(p.channel, { daily_limit: e.target.value === "" ? null : Number(e.target.value) })}
                style={miniInput} />
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ color: theme.textFaint, fontSize: 9 }}>hours</span>
              <input value={p.working_hours ?? ""} placeholder="09:00-18:00" onChange={(e) => updatePolicy(p.channel, { working_hours: e.target.value || null })}
                style={{ ...miniInput, width: 90 }} />
            </span>
            <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ color: theme.textFaint, fontSize: 9 }}>CPM $</span>
              <input type="number" value={p.cpm ?? ""} onChange={(e) => updatePolicy(p.channel, { cpm: e.target.value === "" ? null : Number(e.target.value) })}
                style={miniInput} />
            </span>
          </div>
        ))}
      </Card>

      <SectionTitle>Team</SectionTitle>
      <Card style={{ marginBottom: 16 }}>
        {/* Owner (the manager who created it) */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: `1px solid ${theme.border}` }}>
          <Avatar name={user?.full_name ?? user?.email ?? "?"} />
          <div style={{ flex: 1 }}>
            <div style={{ color: "#fff", fontSize: 11, fontWeight: 600 }}>{user?.full_name ?? user?.email}</div>
            <div style={{ color: theme.textMuted, fontSize: 9 }}>{user?.title ?? "Owner"}</div>
          </div>
          <RolePill label="Owner" highlight />
        </div>

        {/* Assigned members */}
        {assignedRepIds.map((uid) => {
          const u = allUsers.find((x) => x.id === uid);
          return (
            <div key={uid} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: `1px solid ${theme.border}` }}>
              <Avatar name={u?.full_name ?? u?.email ?? uid} />
              <div style={{ flex: 1 }}>
                <div style={{ color: "#fff", fontSize: 11, fontWeight: 600 }}>{u?.full_name ?? u?.email ?? uid}</div>
                <div style={{ color: theme.textMuted, fontSize: 9, textTransform: "capitalize" }}>{u?.title ?? u?.role ?? "member"}</div>
              </div>
              <RolePill label={u?.role ?? "member"} />
              <span onClick={() => setAssignedRepIds((prev) => prev.filter((x) => x !== uid))}
                style={{ color: theme.red, fontSize: 14, cursor: "pointer", marginLeft: 4 }} title="Remove">✕</span>
            </div>
          );
        })}

        {/* Add-member picker: any user not already the owner or assigned */}
        <div style={{ marginTop: 12 }}>
          <AddMember
            candidates={allUsers.filter((u) => u.id !== user?.id && !assignedRepIds.includes(u.id))}
            onAdd={(uid) => setAssignedRepIds((prev) => [...prev, uid])}
          />
        </div>
      </Card>

      <div style={{ display: "flex", gap: 10 }}>
        <Button variant="primary" onClick={save} disabled={busy || !name}>{busy ? "Saving…" : "Save Campaign"}</Button>
        <Button onClick={() => navigate("/campaigns")}>Cancel</Button>
      </div>
    </div>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name.split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div style={{ width: 26, height: 26, borderRadius: "50%", background: "#6a4a8a", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
      {initials}
    </div>
  );
}

function RolePill({ label, highlight }: { label: string; highlight?: boolean }) {
  return (
    <span style={{
      fontSize: 9, padding: "4px 10px", borderRadius: 12, textTransform: "capitalize",
      background: highlight ? "rgba(120,80,220,0.3)" : "rgba(255,255,255,0.05)",
      border: `1px solid ${highlight ? "rgba(150,100,240,0.4)" : theme.borderStrong}`,
      color: highlight ? "#e0d8f0" : theme.textMuted,
    }}>{label}</span>
  );
}

function AddMember({ candidates, onAdd }: { candidates: User[]; onAdd: (id: string) => void }) {
  const [picking, setPicking] = useState(false);
  if (candidates.length === 0 && !picking) {
    return <div style={{ color: theme.textFaint, fontSize: 10 }}>All users assigned (or none available).</div>;
  }
  if (!picking) {
    return <Button onClick={() => setPicking(true)}>+ Add team member</Button>;
  }
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <select defaultValue="" onChange={(e) => { if (e.target.value) { onAdd(e.target.value); setPicking(false); } }}
        style={{ background: "rgba(255,255,255,0.05)", color: theme.textDim, border: `1px solid ${theme.borderStrong}`, borderRadius: 6, padding: "8px 10px", fontSize: 11, fontFamily: theme.font }}>
        <option value="" style={{ background: theme.sidebar }}>Select a user…</option>
        {candidates.map((u) => (
          <option key={u.id} value={u.id} style={{ background: theme.sidebar }}>
            {(u.full_name ?? u.email)} · {u.role}
          </option>
        ))}
      </select>
      <Button onClick={() => setPicking(false)}>Cancel</Button>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 style={{ color: "#fff", fontSize: 14, fontWeight: 700, margin: "0 0 12px 0" }}>{children}</h3>;
}

const miniInput: React.CSSProperties = {
  width: 56,
  background: "rgba(255,255,255,0.05)",
  color: theme.text,
  border: `1px solid ${theme.borderStrong}`,
  borderRadius: 5,
  padding: "4px 6px",
  fontSize: 10,
  fontFamily: theme.font,
};