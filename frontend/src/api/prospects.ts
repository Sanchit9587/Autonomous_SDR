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
};