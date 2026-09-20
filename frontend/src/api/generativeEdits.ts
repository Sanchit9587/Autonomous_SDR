import { api } from "./client";

export interface Suggestion {
  id: string;
  title: string;
  reasoning: string;
  kind: "config_diff" | "action";
  diff?: Record<string, unknown> | null;
  action?: string | null;
}

export interface GenerativeEdits {
  campaign_id: string;
  conversions: number;
  best_channel: string | null;
  best_channel_reply_rate: number | null;
  open_escalations: number;
  stale_discovered: number;
  suggestions: Suggestion[];
}

export const generativeEditsApi = {
  get: (campaignId: string) => api.get<GenerativeEdits>(`/campaigns/${campaignId}/generative-edits`),
};