import { api } from "./client";
import type { AgentDecision, Campaign, CampaignProspectLink, FunnelCounts, Prospect } from "../types";

export interface ProspectRow {
  link: CampaignProspectLink;
  prospect: Prospect;
}

export interface CampaignOverview {
  campaign: Campaign;
  funnel: FunnelCounts;
  open_escalations: number;
}

export const repApi = {
  campaigns: () => api.get<Campaign[]>("/rep/campaigns"),
  overview: (id: string) => api.get<CampaignOverview>(`/rep/campaigns/${id}/overview`),
  prospects: (id: string) => api.get<ProspectRow[]>(`/rep/campaigns/${id}/prospects`),
  activity: (campaignId?: string, limit = 50) =>
    api.get<AgentDecision[]>(`/rep/activity?limit=${limit}${campaignId ? `&campaign_id=${campaignId}` : ""}`),
  escalations: (campaignId?: string) =>
    api.get<AgentDecision[]>(`/rep/escalations${campaignId ? `?campaign_id=${campaignId}` : ""}`),
};