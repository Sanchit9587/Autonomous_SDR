import { api } from "./client";
import type { CampaignAsset } from "../types";

export const assetsApi = {
  list: (campaignId: string) => api.get<CampaignAsset[]>(`/campaigns/${campaignId}/assets`),
  create: (campaignId: string, asset: Partial<CampaignAsset>) =>
    api.post<CampaignAsset>(`/campaigns/${campaignId}/assets`, asset),
};