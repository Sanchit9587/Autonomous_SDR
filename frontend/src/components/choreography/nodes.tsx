import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Channel, Persona, CampaignAsset } from "../../types";
import { theme } from "../../theme";

// Every node type gets these via `data` in addition to its own fields, so
// dropdowns show real campaign personas/assets rather than invented ones.
export interface RefData {
  personas: Persona[];
  assets: CampaignAsset[];
  onChange: (patch: Record<string, unknown>) => void;
  onDelete: () => void;
}

const CHANNEL_META: Record<Channel, { label: string; icon: string; accent: string; border: string }> = {
  email: { label: "Email", icon: "✉", accent: "#a78bfa", border: "#7c4dff" },
  linkedin: { label: "LinkedIn", icon: "in", accent: "#7dd3fc", border: "#4d86ff" },
  sms: { label: "SMS / WA", icon: "◗", accent: "#86efac", border: "#34d399" },
  voice: { label: "Voice call", icon: "☎", accent: "#f0abfc", border: "#c084fc" },
};

const OUTCOME_META: Record<string, { label: string; icon: string; border: string }> = {
  meeting: { label: "Book meeting", icon: "▤", border: "#34d399" },
  escalate: { label: "Escalate to human", icon: "⚑", border: "#fbbf24" },
  suppress: { label: "Suppress", icon: "⊘", border: "#f87171" },
  handoff: { label: "Route to AE", icon: "➜", border: "#38bdf8" },
};

const NODE_BASE: React.CSSProperties = {
  borderRadius: 12,
  padding: "12px 14px",
  minWidth: 220,
  background: theme.cardSolid,
  border: `1.5px solid ${theme.borderStrong}`,
  color: "#efe9fb",
  fontFamily: theme.font,
  fontSize: 12,
  position: "relative",
};

function DeleteButton({ onDelete }: { onDelete: () => void }) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onDelete(); }}
      title="Delete block"
      style={{
        position: "absolute", top: 6, right: 6, width: 18, height: 18, borderRadius: 5,
        border: "none", background: "rgba(255,255,255,0.08)", color: theme.textMuted,
        fontSize: 10, cursor: "pointer", lineHeight: "18px", padding: 0,
      }}
    >
      ✕
    </button>
  );
}

function Header({ icon, iconColor, title, sub }: { icon: string; iconColor: string; title: string; sub?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 8 }}>
      <span style={{
        width: 24, height: 24, borderRadius: 7, display: "grid", placeItems: "center",
        fontSize: 12, fontWeight: 700, flexShrink: 0, background: "rgba(255,255,255,0.1)", color: iconColor,
      }}>{icon}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>{title}</div>
        {sub && <div style={{ fontSize: 10, color: theme.textMuted, marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  width: "100%", padding: "5px 7px", borderRadius: 6, fontSize: 11, fontWeight: 600,
  background: "rgba(255,255,255,0.05)", color: "#efe9fb", border: `1px solid ${theme.borderStrong}`,
};

// Default React Flow handles are ~6px — hard to hit precisely. Bigger visible
// target + (paired with connectionRadius on <ReactFlow> in the page) a bigger
// forgiving hit area makes connecting blocks actually usable.
const handleStyle: React.CSSProperties = {
  width: 16, height: 16, borderRadius: 8,
  background: "#a78bfa", border: "3px solid #1a0f24",
};

export function ActionNode({ data, selected }: NodeProps) {
  const d = data as unknown as RefData & { channel: Channel; personaId?: string; assetId?: string };
  const meta = CHANNEL_META[d.channel] ?? CHANNEL_META.email;
  return (
    <div style={{ ...NODE_BASE, borderColor: selected ? "#c4a6ff" : meta.border }}>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <DeleteButton onDelete={d.onDelete} />
      <Header icon={meta.icon} iconColor={meta.accent} title={meta.label} sub="Action" />
      <div style={{ display: "grid", gap: 6 }}>
        <select style={selectStyle} value={d.personaId ?? ""} onChange={(e) => d.onChange({ personaId: e.target.value || undefined })}>
          <option value="">No persona (generic copy)</option>
          {d.personas.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select style={selectStyle} value={d.assetId ?? ""} onChange={(e) => d.onChange({ assetId: e.target.value || undefined })}>
          <option value="">No asset attached</option>
          {d.assets.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

export function WaitNode({ data, selected }: NodeProps) {
  const d = data as unknown as RefData & { days: number };
  return (
    <div style={{ ...NODE_BASE, borderColor: selected ? "#c4a6ff" : "#4d86ff" }}>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <DeleteButton onDelete={d.onDelete} />
      <Header icon="◷" iconColor="#93b4ff" title="Wait" sub="Logic" />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input type="number" min={1} value={d.days} onChange={(e) => d.onChange({ days: Number(e.target.value) || 1 })}
          style={{ ...selectStyle, width: 60 }} />
        <span style={{ color: theme.textMuted, fontSize: 11 }}>days of silence</span>
      </div>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

export function LoopNode({ data, selected }: NodeProps) {
  const d = data as unknown as RefData & { times: number };
  return (
    <div style={{ ...NODE_BASE, borderColor: selected ? "#c4a6ff" : "#60a5fa" }}>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <DeleteButton onDelete={d.onDelete} />
      <Header icon="↻" iconColor="#93b4ff" title="Follow-up loop" sub="Logic" />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input type="number" min={1} value={d.times} onChange={(e) => d.onChange({ times: Number(e.target.value) || 1 })}
          style={{ ...selectStyle, width: 60 }} />
        <span style={{ color: theme.textMuted, fontSize: 11 }}>× repeats, exits early on any reply</span>
      </div>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

// Only fit_score is wired to a real, per-prospect signal today (set by the
// Research agent). Sentiment/engagement don't exist anywhere in the data
// model, so they're not offered here — see the campaign-health panel for the
// two real *campaign-level* metrics (CAC, LTV:CAC), which aren't per-prospect
// and so can't be a branch condition for an individual prospect.
export function DecisionNode({ data, selected }: NodeProps) {
  const d = data as unknown as RefData & { op: ">=" | "<=" | "=="; value: number };
  return (
    <div style={{ ...NODE_BASE, borderColor: selected ? "#c4a6ff" : "#e0a33a", minWidth: 240 }}>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <DeleteButton onDelete={d.onDelete} />
      <Header icon="◆" iconColor="#e0a33a" title="Decision" sub="ICP fit score" />
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        <span style={{ color: theme.textMuted, fontSize: 11 }}>fit_score</span>
        <select style={{ ...selectStyle, width: 52 }} value={d.op} onChange={(e) => d.onChange({ op: e.target.value })}>
          <option value=">=">≥</option>
          <option value="<=">≤</option>
          <option value="==">=</option>
        </select>
        <input type="number" min={0} max={100} value={d.value} onChange={(e) => d.onChange({ value: Number(e.target.value) })}
          style={{ ...selectStyle, width: 56 }} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 10, fontWeight: 700 }}>
        <div style={{ color: "#34d399" }}>TRUE ↓</div>
        <div style={{ color: "#e0a33a", textAlign: "right" }}>↓ FALSE</div>
      </div>
      <Handle type="source" position={Position.Bottom} id="true" style={{ ...handleStyle, left: "25%", background: "#34d399" }} />
      <Handle type="source" position={Position.Bottom} id="false" style={{ ...handleStyle, left: "75%", background: "#e0a33a" }} />
    </div>
  );
}

export function OutcomeNode({ data, selected }: NodeProps) {
  const d = data as unknown as RefData & { kind: string };
  const meta = OUTCOME_META[d.kind] ?? OUTCOME_META.meeting;
  return (
    <div style={{ ...NODE_BASE, borderColor: selected ? "#c4a6ff" : meta.border }}>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <DeleteButton onDelete={d.onDelete} />
      <Header icon={meta.icon} iconColor="#efe9fb" title="Outcome" sub="Terminal" />
      <select style={selectStyle} value={d.kind} onChange={(e) => d.onChange({ kind: e.target.value })}>
        {Object.entries(OUTCOME_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
      </select>
    </div>
  );
}

export const nodeTypes = {
  action: ActionNode,
  wait: WaitNode,
  loop: LoopNode,
  decision: DecisionNode,
  outcome: OutcomeNode,
};

export const CHANNEL_META_EXPORT = CHANNEL_META;
export const OUTCOME_META_EXPORT = OUTCOME_META;