import { api } from "./client";

export interface ChoreographyNode {
  id: string;
  type: "action" | "wait" | "loop" | "decision" | "outcome";
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface ChoreographyEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
}

export interface ChoreographyGraph {
  nodes: ChoreographyNode[];
  edges: ChoreographyEdge[];
}

export const choreographyApi = {
  get: (campaignId: string) => api.get<ChoreographyGraph>(`/campaigns/${campaignId}/choreography`),
  save: (campaignId: string, graph: ChoreographyGraph) =>
    api.put<ChoreographyGraph>(`/campaigns/${campaignId}/choreography`, graph),
};