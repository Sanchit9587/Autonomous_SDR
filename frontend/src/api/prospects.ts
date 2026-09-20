import { api } from "./client";
import type { AgentDecision, CampaignProspectLink } from "../types";

export const prospectsApi = {
  research: (campaignId: string, linkId: string) =>
    api.post<{ link: CampaignProspectLink; decision: AgentDecision }>(
      `/campaigns/${campaignId}/prospects/${linkId}/research`
    ),
  personalize: (campaignId: string, linkId: string) =>
    api.post<{ decision: AgentDecision }>(
      `/campaigns/${campaignId}/prospects/${linkId}/personalize`
    ),
  converse: (campaignId: string, linkId: string, inbound_message: string) =>
    api.post<{ decision: AgentDecision; personalize_followup: AgentDecision | null }>(
      `/campaigns/${campaignId}/prospects/${linkId}/converse`,
      { inbound_message, trigger: "reply", channel: "email" }
    ),
  decisions: (campaignId: string, linkId: string) =>
    api.get<AgentDecision[]>(`/campaigns/${campaignId}/prospects/${linkId}/decisions`),
  transition: (campaignId: string, linkId: string, to_stage: string) =>
    api.post<CampaignProspectLink>(
      `/campaigns/${campaignId}/prospects/${linkId}/transition`,
      { to_stage }
    ),
  scheduleFollowUp: (campaignId: string, linkId: string, delay_days: number) =>
    api.post<{ scheduled_for: string }>(
      `/campaigns/${campaignId}/prospects/${linkId}/schedule-follow-up`,
      { delay_days }
    ),

  researchDiscovered: (campaignId: string) =>
    api.post<{ processed: number; qualified: number; rejected: number; needs_review: number }>(
      `/campaigns/${campaignId}/research-discovered`
    ),

  uploadCsv: async (
    campaignId: string,
    file: File
  ): Promise<{ added: number; skipped_duplicate: number; skipped_invalid: number; total_rows: number }> => {
    // Multipart upload — can't go through the JSON api helper, so build the
    // request directly (still injecting the JWT).
    const form = new FormData();
    form.append("file", file);
    const base = import.meta.env.VITE_API_BASE_URL ?? "";
    const token = localStorage.getItem("sdr_token");
    const res = await fetch(`${base}/campaigns/${campaignId}/prospects/upload-csv`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
      throw new Error(typeof detail === "string" ? detail : "Upload failed");
    }
    return res.json();
  },
};