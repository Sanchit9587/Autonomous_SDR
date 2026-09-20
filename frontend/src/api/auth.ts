import { api, tokenStore } from "./client";
import type { TokenResponse, User } from "../types";

export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>("/auth/login", { email, password });
    tokenStore.set(res.access_token);
    return res;
  },
  me: () => api.get<User>("/auth/me"),
  logout: () => tokenStore.clear(),
};