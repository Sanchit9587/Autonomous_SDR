import { api } from "./client";
import type { Persona } from "../types";

export const personasApi = {
  list: (campaignId: string) => api.get<Persona[]>(`/campaigns/${campaignId}/personas`),
  create: (campaignId: string, persona: Partial<Persona>) =>
    api.post<Persona>(`/campaigns/${campaignId}/personas`, persona),
};