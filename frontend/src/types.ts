// Types mirroring the backend Pydantic models (core/models). Keep in sync with
// the API; these are the shapes the endpoints return.

export type UserRole = "manager" | "rep" | "admin";
export type CampaignStatus = "draft" | "live" | "paused" | "completed" | "archived";
export type Channel = "linkedin" | "email" | "sms" | "voice";
export type ChannelMode = "automate" | "approval" | "manual";
export type FunnelStage =
  | "discovered" | "researched" | "qualified" | "rejected"
  | "contacted" | "engaged" | "meeting" | "opportunity";
export type Tone =
  | "professional" | "casual" | "consultative" | "direct" | "friendly" | "executive";
export type AssetType = "image" | "pdf" | "video" | "link" | "case_study";

export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  title?: string | null;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ICPFilter {
  keywords?: string | null;
  target_roles: string[];
  geography: string[];
  company_criteria?: string | null;
  company_size_min?: number | null;
  company_size_max?: number | null;
  exclusion_criteria?: string | null;
  sample_profile_urls: string[];
}

export interface AgentSettings {
  enabled: boolean;
  active_prompt_version?: string | null;
  decision_threshold?: number | null;
  tools_allowed: string[];
  escalation_rules?: string | null;
}

export interface ChannelPolicy {
  channel: Channel;
  enabled: boolean;
  mode: ChannelMode;
  daily_limit?: number | null;
  working_hours?: string | null;
  cpm?: number | null;
}

export interface Campaign {
  id: string;
  name: string;
  description?: string | null;
  vision_statement?: string | null;
  owner: string;
  status: CampaignStatus;
  icp: ICPFilter;
  agent_settings: Record<string, AgentSettings>;
  channel_policies: ChannelPolicy[];
  default_channel_priority: Channel[];
  budget?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  target_scale?: number | null;
  pace_per_day?: number | null;
  goals: string[];
  assigned_rep_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface MessageTemplate {
  channel: Channel;
  subject_template?: string | null;
  body_template: string;
  default_asset_ids: string[];
}

export interface FollowUpPolicy {
  max_attempts: number;
  min_days_between: number;
}

export interface Persona {
  id: string;
  campaign_id: string;
  name: string;
  description?: string | null;
  qualification_notes?: string | null;
  importance: number;
  tone: Tone;
  tone_notes?: string | null;
  channel_priority: Channel[];
  templates: Record<string, MessageTemplate>;
  example_messages: Record<string, string[]>;
  follow_up_policy: FollowUpPolicy;
}

export interface CampaignAsset {
  id: string;
  campaign_id: string;
  name: string;
  asset_type: AssetType;
  url: string;
  description?: string | null;
  tags: string[];
}

export interface ProspectProfile {
  name: string;
  linkedin_url?: string | null;
  headline?: string | null;
  location?: string | null;
  position?: string | null;
  company_name?: string | null;
  work_email?: string | null;
  phone_numbers: string[];
  enrichment_status: string;
}

export interface Prospect {
  id: string;
  profile: ProspectProfile;
  created_at: string;
  updated_at: string;
}

export interface CampaignProspectLink {
  id: string;
  campaign_id: string;
  prospect_id: string;
  stage: FunnelStage;
  fit_score?: number | null;
  qualification_reasoning?: string | null;
  persona_id?: string | null;
  human_approved: boolean;
  contact_count: number;
  follow_up_owed: boolean;
  next_follow_up_at?: string | null;
}

export interface AgentDecision {
  id: string;
  campaign_id: string;
  prospect_id: string;
  agent_name: string;
  verdict: string;
  reasoning: string;
  confidence?: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

export type FunnelCounts = Record<FunnelStage, number>;