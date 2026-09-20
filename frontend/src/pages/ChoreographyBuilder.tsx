import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap,
  applyNodeChanges, applyEdgeChanges, addEdge,
  type Node, type Edge, type NodeChange, type EdgeChange, type Connection,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { campaignsApi } from "../api/campaigns";
import { personasApi } from "../api/personas";
import { assetsApi } from "../api/assets";
import { choreographyApi, type ChoreographyNode, type ChoreographyEdge } from "../api/choreography";
import { repApi } from "../api/rep";
import type { Campaign, Persona, CampaignAsset, Channel } from "../types";
import { theme } from "../theme";
import { Button, Spinner, ErrorText } from "../components/ui";
import { nodeTypes } from "../components/choreography/nodes";

let uidCounter = 1;
const uid = () => `n${Date.now()}_${uidCounter++}`;

const PALETTE: { section: string; items: { key: string; label: string; icon: string; border: string; makeType: string; makeData: Record<string, unknown> }[] }[] = [
  {
    section: "ACTIONS", items: [
      { key: "email", label: "Email", icon: "✉", border: "#7c4dff", makeType: "action", makeData: { channel: "email" as Channel } },
      { key: "linkedin", label: "LinkedIn", icon: "in", border: "#4d86ff", makeType: "action", makeData: { channel: "linkedin" as Channel } },
      { key: "sms", label: "SMS / WhatsApp", icon: "◗", border: "#34d399", makeType: "action", makeData: { channel: "sms" as Channel } },
      { key: "voice", label: "Voice call", icon: "☎", border: "#c084fc", makeType: "action", makeData: { channel: "voice" as Channel } },
    ],
  },
  {
    section: "LOGIC", items: [
      { key: "wait", label: "Wait / delay", icon: "◷", border: "#4d86ff", makeType: "wait", makeData: { days: 2 } },
      { key: "loop", label: "Follow-up loop", icon: "↻", border: "#60a5fa", makeType: "loop", makeData: { times: 2 } },
      { key: "decision", label: "Decision (fit score)", icon: "◆", border: "#e0a33a", makeType: "decision", makeData: { op: ">=", value: 70 } },
    ],
  },
  {
    section: "OUTCOMES", items: [
      { key: "meeting", label: "Book meeting", icon: "▤", border: "#34d399", makeType: "outcome", makeData: { kind: "meeting" } },
      { key: "handoff", label: "Route to AE", icon: "➜", border: "#38bdf8", makeType: "outcome", makeData: { kind: "handoff" } },
      { key: "escalate", label: "Escalate to human", icon: "⚑", border: "#fbbf24", makeType: "outcome", makeData: { kind: "escalate" } },
      { key: "suppress", label: "Suppress", icon: "⊘", border: "#f87171", makeType: "outcome", makeData: { kind: "suppress" } },
    ],
  },
];

interface Economics { cac: number | null; avg_deal_value: number | null; ltv_cac_ratio: number | null }

function BuilderInner({ campaignId, campaign }: { campaignId: string; campaign: Campaign }) {
  const navigate = useNavigate();
  const { screenToFlowPosition } = useReactFlow();
  const canvasRef = useRef<HTMLDivElement>(null);

  const [rawNodes, setRawNodes] = useState<ChoreographyNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [assets, setAssets] = useState<CampaignAsset[]>([]);
  const [econ, setEcon] = useState<Economics | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [testFitScore, setTestFitScore] = useState(70);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      choreographyApi.get(campaignId),
      personasApi.list(campaignId),
      assetsApi.list(campaignId),
      repApi.overview(campaignId).catch(() => null),
    ]).then(([graph, p, a, overview]) => {
      setRawNodes(graph.nodes);
      setEdges(graph.edges as Edge[]);
      setPersonas(p);
      setAssets(a);
      if (overview) setEcon({ cac: overview.cac ?? null, avg_deal_value: overview.avg_deal_value ?? null, ltv_cac_ratio: overview.ltv_cac_ratio ?? null });
    }).catch((e) => setError(String((e as Error).message)))
      .finally(() => setLoading(false));
  }, [campaignId]);

  const updateNodeData = useCallback((id: string, patch: Record<string, unknown>) => {
    setRawNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)));
  }, []);

  const deleteNode = useCallback((id: string) => {
    setRawNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
  }, []);

  // React Flow needs live callbacks + reference data injected into each node's
  // `data` to render dropdowns/edit controls — but none of that belongs in
  // what gets saved, so it's computed fresh for display and stripped before save.
  const displayNodes: Node[] = useMemo(() => rawNodes.map((n) => ({
    id: n.id, type: n.type, position: n.position,
    data: { ...n.data, personas, assets, onChange: (patch: Record<string, unknown>) => updateNodeData(n.id, patch), onDelete: () => deleteNode(n.id) },
  })), [rawNodes, personas, assets, updateNodeData, deleteNode]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    // Position/selection/removal changes come through here; re-derive rawNodes
    // by applying them to the display list, then strip back down to domain data.
    setRawNodes((ns) => {
      const applied = applyNodeChanges(changes, ns.map((n) => ({ id: n.id, type: n.type, position: n.position, data: n.data })) as Node[]);
      return applied.map((n) => ({ id: n.id, type: n.type as ChoreographyNode["type"], position: n.position, data: n.data }));
    });
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => setEdges((es) => applyEdgeChanges(changes, es)), []);
  const onConnect = useCallback((conn: Connection) => setEdges((es) => addEdge(conn, es)), []);

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/json");
    if (!raw) return;
    const item = JSON.parse(raw) as { makeType: string; makeData: Record<string, unknown> };
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const node: ChoreographyNode = { id: uid(), type: item.makeType as ChoreographyNode["type"], position, data: item.makeData };
    setRawNodes((ns) => [...ns, node]);
  }, [screenToFlowPosition]);

  const onDragOver = useCallback((event: React.DragEvent) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }, []);

  const save = async () => {
    setSaving(true); setError(null); setNotice(null);
    try {
      const payload = { nodes: rawNodes, edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle })) as ChoreographyEdge[] };
      await choreographyApi.save(campaignId, payload);
      setNotice("Saved.");
    } catch (e) { setError(String((e as Error).message)); }
    finally { setSaving(false); }
  };

  // Walks the graph from every node with no incoming edge, evaluating decision
  // nodes against the test fit score, and returns the set of node ids on the
  // resulting path(s) — the only real per-prospect signal we have is fit_score,
  // so that's the only thing this can honestly simulate.
  const highlightedPath = useMemo(() => {
    const byId = new Map(rawNodes.map((n) => [n.id, n]));
    const outgoing = new Map<string, Edge[]>();
    edges.forEach((e) => { outgoing.set(e.source, [...(outgoing.get(e.source) ?? []), e]); });
    const hasIncoming = new Set(edges.map((e) => e.target));
    const roots = rawNodes.filter((n) => !hasIncoming.has(n.id));

    const visited = new Set<string>();
    const walk = (id: string) => {
      if (visited.has(id)) return;
      visited.add(id);
      const node = byId.get(id);
      const outs = outgoing.get(id) ?? [];
      if (!node) return;
      if (node.type === "decision") {
        const d = node.data as { op: ">=" | "<=" | "=="; value: number };
        const result = d.op === ">=" ? testFitScore >= d.value : d.op === "<=" ? testFitScore <= d.value : testFitScore === d.value;
        const wanted = result ? "true" : "false";
        const edge = outs.find((e) => e.sourceHandle === wanted);
        if (edge) walk(edge.target);
      } else {
        outs.forEach((e) => walk(e.target));
      }
    };
    roots.forEach((r) => walk(r.id));
    return visited;
  }, [rawNodes, edges, testFitScore]);

  const previewNodes = useMemo(() => displayNodes.map((n) => ({
    ...n,
    style: highlightedPath.has(n.id) ? { boxShadow: "0 0 0 2px #4ade80" } : undefined,
  })), [displayNodes, highlightedPath]);

  if (loading) return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: theme.bg }}><Spinner /></div>;

  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateRows: "auto 1fr", background: theme.bg, color: "#efe9fb", fontFamily: theme.font }}>
      <header style={{ display: "flex", alignItems: "center", gap: 16, padding: "14px 22px", borderBottom: `1px solid ${theme.border}`, background: theme.sidebarGradient }}>
        <span style={{ color: theme.purpleLight, fontSize: 13, fontWeight: 600, cursor: "pointer" }} onClick={() => navigate(`/campaigns/${campaignId}`)}>← Back to Campaign</span>
        <span style={{ width: 1, height: 22, background: theme.borderStrong }} />
        <span style={{ fontSize: 18, fontWeight: 800 }}>Choreography Builder</span>
        <span style={{ color: theme.textMuted, fontSize: 12 }}>{campaign.name}</span>
        <span style={{ flex: 1 }} />
        {error && <ErrorText>{error}</ErrorText>}
        {notice && <span style={{ color: theme.green, fontSize: 12 }}>{notice}</span>}
        <Button variant="primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "💾 Save"}</Button>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "260px minmax(0,1fr)", minHeight: 0 }}>
        <aside style={{ borderRight: `1px solid ${theme.border}`, padding: "16px 14px", overflowY: "auto" }}>
          <div style={{ fontSize: 10, letterSpacing: "0.12em", color: theme.textFaint, fontWeight: 700, marginBottom: 10 }}>CAMPAIGN HEALTH</div>
          <div style={{ padding: 12, borderRadius: 10, border: `1px solid ${theme.border}`, background: "rgba(255,255,255,0.02)", marginBottom: 18, fontSize: 11 }}>
            <Row label="CAC" value={econ?.cac != null ? `$${econ.cac.toFixed(2)}` : "—"} />
            <Row label="Avg. deal value" value={econ?.avg_deal_value != null ? `$${econ.avg_deal_value.toFixed(2)}` : "—"} />
            <Row label="LTV : CAC" value={econ?.ltv_cac_ratio != null ? `${econ.ltv_cac_ratio.toFixed(1)}×` : "—"} />
            <div style={{ color: theme.textFaint, fontSize: 9, marginTop: 8, lineHeight: 1.4 }}>
              Campaign-wide, not per-prospect — can't be a Decision branch condition for an individual lead.
            </div>
          </div>

          <div style={{ fontSize: 10, letterSpacing: "0.12em", color: theme.textFaint, fontWeight: 700, marginBottom: 10 }}>TEST WITH FIT SCORE</div>
          <div style={{ padding: 12, borderRadius: 10, border: `1px solid ${theme.border}`, background: "rgba(255,255,255,0.02)", marginBottom: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 6 }}>
              <span style={{ color: theme.textMuted }}>fit_score</span>
              <span style={{ fontWeight: 700 }}>{testFitScore}/100</span>
            </div>
            <input type="range" min={0} max={100} value={testFitScore} onChange={(e) => setTestFitScore(Number(e.target.value))} style={{ width: "100%" }} />
            <div style={{ color: theme.textFaint, fontSize: 9, marginTop: 8, lineHeight: 1.4 }}>
              Highlights which path a prospect with this ICP fit score would take through your Decision blocks.
            </div>
          </div>

          {PALETTE.map((group) => (
            <div key={group.section} style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 10, letterSpacing: "0.12em", color: theme.textFaint, fontWeight: 700, marginBottom: 8 }}>{group.section}</div>
              <div style={{ display: "grid", gap: 6 }}>
                {group.items.map((it) => (
                  <div key={it.key} draggable
                    onDragStart={(e) => e.dataTransfer.setData("application/json", JSON.stringify(it))}
                    style={{
                      display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: 8, cursor: "grab",
                      background: "rgba(255,255,255,0.03)", border: `1px solid ${it.border}55`, fontSize: 12, fontWeight: 600,
                    }}>
                    <span style={{ width: 18, height: 18, borderRadius: 5, background: "rgba(255,255,255,0.08)", display: "grid", placeItems: "center", fontSize: 10 }}>{it.icon}</span>
                    {it.label}
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div style={{ padding: 10, borderRadius: 10, border: `1px dashed ${theme.borderStrong}`, color: theme.textFaint, fontSize: 10, lineHeight: 1.5 }}>
            Drag a block onto the canvas. Drag from a block's bottom handle to another block's top to connect them. A Decision block has two bottom handles — left is TRUE, right is FALSE.
          </div>
        </aside>

        <main ref={canvasRef} onDrop={onDrop} onDragOver={onDragOver} style={{ position: "relative" }}>
          <ReactFlow
            nodes={previewNodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            connectionRadius={40}
            fitView
            colorMode="dark"
          >
            <Background color={theme.borderStrong} gap={20} />
            <Controls />
            <MiniMap pannable zoomable style={{ background: theme.sidebar }} />
          </ReactFlow>
        </main>
      </div>
    </div>
  );
}

export function ChoreographyBuilderPage() {
  const { id } = useParams();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    campaignsApi.get(id).then(setCampaign).catch((e) => setError(String((e as Error).message)));
  }, [id]);

  if (error) return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: theme.bg }}><ErrorText>{error}</ErrorText></div>;
  if (!campaign || !id) return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: theme.bg }}><Spinner /></div>;

  return (
    <ReactFlowProvider>
      <BuilderInner campaignId={id} campaign={campaign} />
    </ReactFlowProvider>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
      <span style={{ color: theme.textMuted }}>{label}</span>
      <span style={{ fontWeight: 700 }}>{value}</span>
    </div>
  );
}