import { api } from "./client";
import type { Campaign, CampaignProspectLink, FunnelCounts, Prospect } from "../types";

export interface CreateCampaignBody {
  name: string;
  owner: string;
  description?: string;
  vision_statement?: string;
  icp?: Partial<Campaign["icp"]>;
  budget?: number;
  start_date?: string;
  end_date?: string;
  target_scale?: number;
  pace_per_day?: number;
  goals?: string[];
  channel_policies?: Campaign["channel_policies"];
  default_channel_priority?: Campaign["default_channel_priority"];
  agent_settings?: Campaign["agent_settings"];
}

export const campaignsApi = {
  list: () => api.get<Campaign[]>("/campaigns"),
  get: (id: string) => api.get<Campaign>(`/campaigns/${id}`),
  create: (body: CreateCampaignBody) => api.post<Campaign>("/campaigns", body),
  update: (id: string, body: Partial<CreateCampaignBody> & { assigned_rep_ids?: string[] }) =>
    api.patch<Campaign>(`/campaigns/${id}`, body),

  activate: (id: string) => api.post<Campaign>(`/campaigns/${id}/activate`),
  pause: (id: string) => api.post<Campaign>(`/campaigns/${id}/pause`),
  resume: (id: string) => api.post<Campaign>(`/campaigns/${id}/resume`),
  complete: (id: string) => api.post<Campaign>(`/campaigns/${id}/complete`),
  archive: (id: string) => api.post<Campaign>(`/campaigns/${id}/archive`),
  duplicate: (id: string) => api.post<Campaign>(`/campaigns/${id}/duplicate`),

  funnel: (id: string) => api.get<FunnelCounts>(`/campaigns/${id}/funnel`),

  addProspect: (id: string, prospect: Prospect) =>
    api.post<CampaignProspectLink>(`/campaigns/${id}/prospects`, prospect),
};