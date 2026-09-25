import axios from "axios";

const PRODUCTION_API_BASE_URL = "https://lead-generation-backend-nu.vercel.app";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "production" ? PRODUCTION_API_BASE_URL : "http://localhost:8000")
).replace(/\/$/, "");

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
}

export interface AuthResponse extends AuthTokens {
  user: User;
}

export async function registerAccount(payload: {
  email: string;
  password: string;
  full_name?: string;
  workspace_name: string;
}): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/register", payload);
  return data;
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/login", payload);
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}

export type WorkspacePlan = "free" | "starter" | "professional" | "agency" | "enterprise";

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: WorkspacePlan;
  limits: Record<string, number | undefined>;
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const { data } = await api.get<Workspace[]>("/workspaces");
  return data;
}

export async function createWorkspace(name: string, plan: WorkspacePlan = "free"): Promise<Workspace> {
  const { data } = await api.post<Workspace>("/workspaces", { name, plan });
  return data;
}

export async function updateWorkspace(
  workspaceId: string,
  payload: { plan?: WorkspacePlan; limits?: Record<string, number> }
): Promise<Workspace> {
  const { data } = await api.patch<Workspace>(`/workspaces/${workspaceId}`, payload);
  return data;
}

export type WorkspaceRole = "owner" | "admin" | "member" | "viewer";

export interface WorkspaceMember {
  id: string;
  user_id: string;
  workspace_id: string;
  role: WorkspaceRole;
  email: string | null;
}

export async function listWorkspaceMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  const { data } = await api.get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
  return data;
}

export async function addWorkspaceMember(
  workspaceId: string,
  email: string,
  role: WorkspaceRole = "member"
): Promise<WorkspaceMember> {
  const { data } = await api.post<WorkspaceMember>(`/workspaces/${workspaceId}/members`, { email, role });
  return data;
}

export async function updateWorkspaceMemberRole(
  workspaceId: string,
  memberId: string,
  role: WorkspaceRole
): Promise<WorkspaceMember> {
  const { data } = await api.patch<WorkspaceMember>(`/workspaces/${workspaceId}/members/${memberId}`, { role });
  return data;
}

export async function removeWorkspaceMember(workspaceId: string, memberId: string): Promise<void> {
  await api.delete(`/workspaces/${workspaceId}/members/${memberId}`);
}

// ---------------------------------------------------------------------------
// Admin (superuser only)
// ---------------------------------------------------------------------------

export async function listAllUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>("/admin/users");
  return data;
}

export async function updateUserSuperuser(userId: string, isSuperuser: boolean): Promise<User> {
  const { data } = await api.patch<User>(`/admin/users/${userId}/superuser`, { is_superuser: isSuperuser });
  return data;
}

export async function getAdminProviderPanel(): Promise<ProviderHealth[]> {
  const { data } = await api.get<ProviderHealth[]>("/admin/providers");
  return data;
}

export interface SourceCount {
  provider: string;
  count: number;
}

export interface CampaignSummary {
  campaign_id: string;
  name: string;
  sent: number;
  opened: number;
  clicked: number;
  replied: number;
  bounced: number;
}

export interface AnalyticsOverview {
  total_companies: number;
  total_contacts: number;
  verified_emails: number;
  high_intent_leads: number;
  high_icp_leads: number | null;
  meetings: number;
  conversions: number;
  emails_sent: number;
  delivered: number;
  bounced: number;
  opened: number;
  clicked: number;
  replied: number;
  delivery_rate: number | null;
  bounce_rate: number | null;
  open_rate: number | null;
  click_rate: number | null;
  reply_rate: number | null;
  positive_reply_rate: number | null;
  total_provider_cost: number;
  cost_per_verified_lead: number | null;
  cost_per_qualified_lead: number | null;
  top_sources: SourceCount[];
  top_campaigns: CampaignSummary[];
}

export async function getAnalyticsOverview(workspaceId: string): Promise<AnalyticsOverview> {
  const { data } = await api.get<AnalyticsOverview>("/analytics/overview", {
    params: { workspace_id: workspaceId },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Companies
// ---------------------------------------------------------------------------

export interface CompanySource {
  id: string;
  provider: string;
  external_id: string | null;
  source_url: string | null;
  source_type: string;
  retrieved_at: string;
}

export interface Company {
  id: string;
  name: string | null;
  domain: string | null;
  website: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  industry: string | null;
  category: string | null;
  employee_count: number | null;
  description: string | null;
  linkedin_url: string | null;
  social_urls: Record<string, string>;
  field_provenance: Record<string, unknown>;
  first_seen: string;
  last_seen: string;
}

export async function listCompanies(
  workspaceId: string,
  params: { search?: string; limit?: number; offset?: number } = {}
): Promise<Company[]> {
  const { data } = await api.get<Company[]>("/companies", {
    params: { workspace_id: workspaceId, ...params },
  });
  return data;
}

export async function getCompany(workspaceId: string, companyId: string): Promise<Company> {
  const { data } = await api.get<Company>(`/companies/${companyId}`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function listCompanySources(
  workspaceId: string,
  companyId: string
): Promise<CompanySource[]> {
  const { data } = await api.get<CompanySource[]>(`/companies/${companyId}/sources`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export interface DecisionMakerSearchResponse {
  contacts_created: number;
  contacts_matched: number;
  contacts: Contact[];
}

export async function findDecisionMakers(
  workspaceId: string,
  companyId: string,
  targetTitles?: string[]
): Promise<DecisionMakerSearchResponse> {
  const { data } = await api.post<DecisionMakerSearchResponse>(
    `/companies/${companyId}/decision-makers`,
    targetTitles ? { target_titles: targetTitles } : {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface IntentSignal {
  id: string;
  company_id: string;
  signal_type: string;
  provider: string;
  source: string;
  source_url: string;
  signal_text: string | null;
  confidence: number | null;
  detected_at: string;
}

export interface IntentScore {
  company_id: string;
  score: number;
  signal_count: number;
  signals: IntentSignal[];
}

export async function listIntentSignals(workspaceId: string, companyId: string): Promise<IntentSignal[]> {
  const { data } = await api.get<IntentSignal[]>(`/companies/${companyId}/intent-signals`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function getIntentScore(workspaceId: string, companyId: string): Promise<IntentScore> {
  const { data } = await api.get<IntentScore>(`/companies/${companyId}/intent-score`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Leads (contacts) + CRM
// ---------------------------------------------------------------------------

export type LeadStatus =
  | "new"
  | "verified"
  | "ready_for_outreach"
  | "contacted"
  | "opened"
  | "clicked"
  | "replied"
  | "interested"
  | "meeting"
  | "won"
  | "lost"
  | "unsubscribed"
  | "bounced";

export interface Contact {
  id: string;
  company_id: string | null;
  company_name: string | null;
  company_phone: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  job_title: string | null;
  department: string | null;
  seniority: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  industry: string | null;
  sub_industry: string | null;
  company_headcount: string | null;
  company_revenue: string | null;
  status: LeadStatus;
  field_provenance: Record<string, unknown>;
  /** True only when a source (currently just Apollo) supports the on-demand
   * /reveal action — false for masked leads with no API-based unlock
   * (e.g. Smartlead), so the UI never shows a Reveal button that would
   * just fail. */
  revealable: boolean;
  latest_qualification: LeadQualificationSummary | null;
  /** WhatsApp-style read-receipt signal: "sent" (one tick), "opened" (two
   * ticks), or null if no campaign has ever emailed this lead. */
  email_track_status: "sent" | "opened" | null;
  first_seen: string;
  last_seen: string;
}

export type QualificationTier = "A" | "B" | "C" | "D" | "E";

export interface LeadQualificationSummary {
  tier: QualificationTier;
  composite_score: number;
  confidence: number;
  scored_at: string;
}

export interface LeadQualificationRead extends LeadQualificationSummary {
  id: string;
  contact_id: string;
  provider: string;
  model: string;
  prompt_version: string;
  score_version: string;
  tier_rationale: string;
  dimensions: Record<string, { score: number; confidence: number; reasoning: string }>;
  evidence: {
    dimension: string;
    claim: string;
    observation: string;
    source_platform: string;
    source_field_or_url: string;
    inference_type: "observed" | "inferred";
    strength: "strong" | "moderate" | "weak";
  }[];
  overrides_triggered: string[];
  disqualifier: string | null;
  missing_data: { field: string; why_it_matters: string; how_to_obtain: string }[];
  enrichment_priority: "high" | "medium" | "low" | null;
  recommended_channel: "email" | "call" | "linkedin" | "multi" | null;
  recommended_angle: string | null;
  objection_to_expect: string | null;
  estimated_deal_band: "small" | "mid" | "large" | "unknown" | null;
  next_review_date: string | null;
  human_review_required: boolean;
  human_review_reason: string | null;
  uncertainty_notes: string | null;
}

export async function qualifyLead(workspaceId: string, contactId: string): Promise<LeadQualificationRead> {
  const { data } = await api.post<LeadQualificationRead>(
    `/leads/${contactId}/qualify`,
    {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface BatchQualifyResponse {
  scheduled: number;
  already_scored: number;
  total: number;
}

export async function qualifyBatch(workspaceId: string, batchId: string): Promise<BatchQualifyResponse> {
  const { data } = await api.post<BatchQualifyResponse>(
    `/search-batches/${batchId}/qualify-all`,
    {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface BatchRevealResponse {
  revealed: number;
  skipped: number;
  failed: number;
  total: number;
}

export async function revealBatch(workspaceId: string, batchId: string): Promise<BatchRevealResponse> {
  const { data } = await api.post<BatchRevealResponse>(
    `/search-batches/${batchId}/reveal-all`,
    {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface BatchPhoneEnrichResponse {
  requested: number;
  skipped: number;
  failed: number;
  total: number;
}

export async function enrichPhonesBatch(
  workspaceId: string,
  batchId: string
): Promise<BatchPhoneEnrichResponse> {
  const { data } = await api.post<BatchPhoneEnrichResponse>(
    `/search-batches/${batchId}/enrich-phones`,
    {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export async function listLeads(
  workspaceId: string,
  params: {
    status?: LeadStatus;
    tag_id?: string;
    company_id?: string;
    search?: string;
    sort_by?: string;
    sort_dir?: "asc" | "desc";
    limit?: number;
    offset?: number;
  } = {}
): Promise<Contact[]> {
  const { data } = await api.get<Contact[]>("/leads", {
    params: { workspace_id: workspaceId, ...params },
  });
  return data;
}

export async function getLead(workspaceId: string, contactId: string): Promise<Contact> {
  const { data } = await api.get<Contact>(`/leads/${contactId}`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function updateLeadStatus(
  workspaceId: string,
  contactId: string,
  status: LeadStatus
): Promise<Contact> {
  const { data } = await api.patch<Contact>(
    `/leads/${contactId}/status`,
    { status },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface BulkStatusUpdateResponse {
  updated: number;
  not_found: number;
}

export async function bulkUpdateLeadStatus(
  workspaceId: string,
  contactIds: string[],
  status: LeadStatus
): Promise<BulkStatusUpdateResponse> {
  const { data } = await api.patch<BulkStatusUpdateResponse>(
    "/leads/bulk-status",
    { contact_ids: contactIds, status },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface AIGeneration {
  id: string;
  contact_id: string;
  provider: string;
  model: string;
  prompt_version: string;
  source_fields_used: string[];
  subject: string | null;
  opening_line: string | null;
  body: string | null;
  cta: string | null;
  outreach_angle: string | null;
  personalization_source: string | null;
  signal_id: string | null;
  source_url: string | null;
  generated_at: string;
}

export async function personalizeLead(workspaceId: string, contactId: string): Promise<AIGeneration> {
  const { data } = await api.post<AIGeneration>(
    `/leads/${contactId}/personalize`,
    {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export async function listLeadPersonalizations(
  workspaceId: string,
  contactId: string
): Promise<AIGeneration[]> {
  const { data } = await api.get<AIGeneration[]>(`/leads/${contactId}/personalizations`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export interface Note {
  id: string;
  contact_id: string;
  author_user_id: string | null;
  text: string;
  created_at: string;
}

export async function listLeadNotes(workspaceId: string, contactId: string): Promise<Note[]> {
  const { data } = await api.get<Note[]>(`/leads/${contactId}/notes`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function createLeadNote(workspaceId: string, contactId: string, text: string): Promise<Note> {
  const { data } = await api.post<Note>(
    `/leads/${contactId}/notes`,
    { text },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface Task {
  id: string;
  contact_id: string;
  title: string;
  due_at: string | null;
  completed: boolean;
  created_at: string;
}

export async function listLeadTasks(workspaceId: string, contactId: string): Promise<Task[]> {
  const { data } = await api.get<Task[]>(`/leads/${contactId}/tasks`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function createLeadTask(
  workspaceId: string,
  contactId: string,
  payload: { title: string; due_at?: string }
): Promise<Task> {
  const { data } = await api.post<Task>(`/leads/${contactId}/tasks`, payload, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function updateLeadTask(
  workspaceId: string,
  contactId: string,
  taskId: string,
  payload: { completed?: boolean; title?: string; due_at?: string }
): Promise<Task> {
  const { data } = await api.patch<Task>(`/leads/${contactId}/tasks/${taskId}`, payload, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export interface Tag {
  id: string;
  name: string;
}

export async function listTags(workspaceId: string): Promise<Tag[]> {
  const { data } = await api.get<Tag[]>("/tags", { params: { workspace_id: workspaceId } });
  return data;
}

export async function createTag(workspaceId: string, name: string): Promise<Tag> {
  const { data } = await api.post<Tag>("/tags", { name }, { params: { workspace_id: workspaceId } });
  return data;
}

export async function tagLead(workspaceId: string, contactId: string, tagId: string): Promise<void> {
  await api.post(
    "/leads/bulk-tag",
    { contact_ids: [contactId], tag_id: tagId },
    { params: { workspace_id: workspaceId } }
  );
}

// ---------------------------------------------------------------------------
// Discovery / search
// ---------------------------------------------------------------------------

export type ProviderCategory = "company_discovery" | "person_discovery" | "ai" | "email_sender";

export interface ProviderConfig {
  id: string;
  provider: string;
  category: ProviderCategory;
  enabled: boolean;
  priority: number;
  monthly_free_quota: number | null;
  config: Record<string, unknown>;
}

export async function listProviders(): Promise<ProviderConfig[]> {
  const { data } = await api.get<ProviderConfig[]>("/providers");
  return data;
}

export async function updateProviderConfig(
  providerConfigId: string,
  payload: { enabled?: boolean; priority?: number; monthly_free_quota?: number }
): Promise<ProviderConfig> {
  const { data } = await api.patch<ProviderConfig>(`/providers/${providerConfigId}`, payload);
  return data;
}

export interface ProviderUsage {
  id: string;
  provider: string;
  category: ProviderCategory;
  operation: string;
  workspace_id: string | null;
  success: boolean;
  error: string | null;
  duration_ms: number;
  records_returned: number | null;
  estimated_cost: number | null;
  occurred_at: string;
}

export async function listProviderUsage(params: {
  provider?: string;
  category?: ProviderCategory;
  limit?: number;
} = {}): Promise<ProviderUsage[]> {
  const { data } = await api.get<ProviderUsage[]>("/providers/usage", { params });
  return data;
}

export interface ProviderHealth {
  provider: string;
  category: ProviderCategory;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  calls_this_month: number;
  monthly_free_quota: number | null;
  quota_remaining: number | null;
}

export async function getProviderHealth(): Promise<ProviderHealth[]> {
  const { data } = await api.get<ProviderHealth[]>("/providers/health");
  return data;
}

export interface DiscoveryCriteria {
  keywords?: string;
  industry?: string;
  country?: string;
  state?: string;
  city?: string;
  company_name?: string;
  domain?: string;
  employee_count_min?: number;
  employee_count_max?: number;
  job_titles?: string[];
  seniorities?: string[];
  limit?: number;
  /** Smartlead-specific: the campaign to pull existing leads from. */
  campaign_id?: string;
  /** Passthrough filters a specific provider understands (e.g. Smartlead's emailStatus). */
  extra_filters?: Record<string, unknown>;
}

export interface SearchExecuteResponse {
  provider: string;
  category: ProviderCategory;
  /** null when the search returned nothing — no batch is created for a
   * zero-result run. */
  batch_id: string | null;
  companies_created: number;
  companies_matched: number;
  contacts_created: number;
  contacts_matched: number;
  companies: Company[];
  contacts: Contact[];
}

export async function executeSearch(payload: {
  workspace_id: string;
  provider: string;
  category: ProviderCategory;
  criteria: DiscoveryCriteria;
}): Promise<SearchExecuteResponse> {
  const { data } = await api.post<SearchExecuteResponse>("/search/execute", payload);
  return data;
}

export async function parseProspectPrompt(payload: {
  workspace_id: string;
  provider: string;
  prompt: string;
}): Promise<{ criteria: DiscoveryCriteria }> {
  const { data } = await api.post<{ criteria: DiscoveryCriteria }>("/search/parse-prompt", payload);
  return data;
}

export interface SearchBatch {
  id: string;
  sequence: number;
  provider: string;
  category: ProviderCategory;
  criteria_snapshot: Record<string, unknown>;
  companies_created: number;
  companies_matched: number;
  contacts_created: number;
  contacts_matched: number;
  created_at: string;
}

export interface SearchBatchDetail extends SearchBatch {
  contacts: Contact[];
}

export async function listSearchBatches(
  workspaceId: string,
  params: { limit?: number; offset?: number } = {}
): Promise<SearchBatch[]> {
  const { data } = await api.get<SearchBatch[]>("/search-batches", {
    params: { workspace_id: workspaceId, ...params },
  });
  return data;
}

export async function getSearchBatch(workspaceId: string, batchId: string): Promise<SearchBatchDetail> {
  const { data } = await api.get<SearchBatchDetail>(`/search-batches/${batchId}`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export interface RevealResponse {
  contact: Contact;
  revealed: boolean;
}

export async function revealLead(workspaceId: string, contactId: string): Promise<RevealResponse> {
  const { data } = await api.post<RevealResponse>(
    `/leads/${contactId}/reveal`,
    {},
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

// ---------------------------------------------------------------------------
// Campaigns
// ---------------------------------------------------------------------------

export type CampaignStatus = "draft" | "scheduled" | "running" | "paused" | "completed" | "cancelled";

export interface CampaignStep {
  id: string;
  step_number: number;
  delay_days: number;
  subject: string;
  body: string;
  active: boolean;
}

export interface Campaign {
  id: string;
  name: string;
  status: CampaignStatus;
  from_name: string | null;
  from_email: string;
  reply_to: string | null;
  daily_limit: number;
  timezone: string;
  steps: CampaignStep[];
}

export async function listCampaigns(workspaceId: string): Promise<Campaign[]> {
  const { data } = await api.get<Campaign[]>("/campaigns", { params: { workspace_id: workspaceId } });
  return data;
}

export async function getCampaign(workspaceId: string, campaignId: string): Promise<Campaign> {
  const { data } = await api.get<Campaign>(`/campaigns/${campaignId}`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function createCampaign(
  workspaceId: string,
  payload: {
    name: string;
    from_name?: string;
    from_email: string;
    reply_to?: string;
    daily_limit?: number;
    timezone?: string;
  }
): Promise<Campaign> {
  const { data } = await api.post<Campaign>("/campaigns", payload, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function addCampaignStep(
  workspaceId: string,
  campaignId: string,
  payload: { step_number: number; delay_days?: number; subject: string; body: string; active?: boolean }
): Promise<CampaignStep> {
  const { data } = await api.post<CampaignStep>(`/campaigns/${campaignId}/steps`, payload, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function updateCampaignStep(
  workspaceId: string,
  campaignId: string,
  stepId: string,
  payload: Partial<{ step_number: number; delay_days: number; subject: string; body: string; active: boolean }>
): Promise<CampaignStep> {
  const { data } = await api.patch<CampaignStep>(`/campaigns/${campaignId}/steps/${stepId}`, payload, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function deleteCampaignStep(workspaceId: string, campaignId: string, stepId: string): Promise<void> {
  await api.delete(`/campaigns/${campaignId}/steps/${stepId}`, {
    params: { workspace_id: workspaceId },
  });
}

export interface EnrollResponse {
  enrolled: number;
  already_enrolled: number;
  not_found: number;
  sent?: number;
  failed?: number;
  suppressed?: number;
}

export async function enrollContacts(
  workspaceId: string,
  campaignId: string,
  contactIds: string[],
  emailSetupId?: string
): Promise<EnrollResponse> {
  const { data } = await api.post<EnrollResponse>(
    `/campaigns/${campaignId}/enroll`,
    {
      contact_ids: contactIds,
      ...(emailSetupId ? { email_setup_id: emailSetupId } : {}),
    },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export async function enrollBatches(
  workspaceId: string,
  campaignId: string,
  batchIds: string[],
  emailSetupId: string,
  content: { subject: string; body: string }
): Promise<EnrollResponse> {
  const { data } = await api.post<EnrollResponse>(
    `/campaigns/${campaignId}/enroll`,
    {
      batch_ids: batchIds,
      email_setup_id: emailSetupId,
      subject: content.subject,
      body: content.body,
    },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

async function setCampaignLifecycle(
  workspaceId: string,
  campaignId: string,
  action: "start" | "pause" | "resume" | "cancel"
): Promise<Campaign> {
  const { data } = await api.post<Campaign>(`/campaigns/${campaignId}/${action}`, null, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export const startCampaign = (workspaceId: string, campaignId: string) =>
  setCampaignLifecycle(workspaceId, campaignId, "start");
export const pauseCampaign = (workspaceId: string, campaignId: string) =>
  setCampaignLifecycle(workspaceId, campaignId, "pause");
export const resumeCampaign = (workspaceId: string, campaignId: string) =>
  setCampaignLifecycle(workspaceId, campaignId, "resume");
export const cancelCampaign = (workspaceId: string, campaignId: string) =>
  setCampaignLifecycle(workspaceId, campaignId, "cancel");

export interface ProcessCampaignResponse {
  sent: number;
  suppressed: number;
  completed: number;
  failed: number;
  skipped_no_quota: boolean;
}

export async function processCampaignNow(
  workspaceId: string,
  campaignId: string
): Promise<ProcessCampaignResponse> {
  const { data } = await api.post<ProcessCampaignResponse>(`/campaigns/${campaignId}/process`, null, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export interface PreviewResponse {
  subject: string;
  body: string;
  variables_filled: string[];
  variables_empty: string[];
  unrecognized_variables: string[];
}

export async function previewCampaignStep(
  workspaceId: string,
  campaignId: string,
  contactId: string,
  stepNumber: number
): Promise<PreviewResponse> {
  const { data } = await api.post<PreviewResponse>(
    `/campaigns/${campaignId}/preview`,
    { contact_id: contactId, step_number: stepNumber },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

export interface CampaignReport {
  campaign_id: string;
  name: string;
  status: CampaignStatus;
  contacts_enrolled: number;
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  replied: number;
  positive_replies: number;
  bounced: number;
  unsubscribed: number;
  meetings: number;
  won: number;
  delivery_rate: number | null;
  bounce_rate: number | null;
  open_rate: number | null;
  click_rate: number | null;
  reply_rate: number | null;
  positive_reply_rate: number | null;
}

export async function getCampaignReport(workspaceId: string, campaignId: string): Promise<CampaignReport> {
  const { data } = await api.get<CampaignReport>(`/campaigns/${campaignId}/report`, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Suppressions
// ---------------------------------------------------------------------------

export type SuppressionReason = "unsubscribe" | "bounce" | "manual" | "complaint" | "reply_opt_out";

export interface Suppression {
  id: string;
  email: string;
  reason: SuppressionReason;
  campaign_id: string | null;
  created_at: string;
}

export async function listSuppressions(workspaceId: string): Promise<Suppression[]> {
  const { data } = await api.get<Suppression[]>("/suppressions", {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function createSuppression(
  workspaceId: string,
  email: string,
  reason: SuppressionReason = "manual"
): Promise<Suppression> {
  const { data } = await api.post<Suppression>(
    "/suppressions",
    { email, reason },
    { params: { workspace_id: workspaceId } }
  );
  return data;
}

// ---------------------------------------------------------------------------
// Email Setup (SMTP accounts)
// ---------------------------------------------------------------------------

export interface EmailSetup {
  id: string;
  name: string;
  smtp_host: string;
  smtp_port: number;
  smtp_email: string;
  smtp_use_tls: boolean;
  is_default: boolean;
  has_password: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailSetupDefaults {
  name: string;
  smtp_host: string;
  smtp_port: number;
  smtp_email: string;
  smtp_password: string;
  smtp_use_tls: boolean;
}

export interface EmailSetupCreatePayload {
  name: string;
  smtp_host: string;
  smtp_port: number;
  smtp_email: string;
  smtp_password: string;
  smtp_use_tls?: boolean;
  is_default?: boolean;
}

export interface EmailSetupUpdatePayload {
  name?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_email?: string;
  smtp_password?: string;
  smtp_use_tls?: boolean;
  is_default?: boolean;
}

export interface EmailSetupImportResult {
  created: number;
  skipped: number;
  errors: { row_number: number; message: string }[];
}

export async function getEmailSetupDefaults(): Promise<EmailSetupDefaults> {
  const { data } = await api.get<EmailSetupDefaults>("/email-setups/defaults");
  return data;
}

export async function listEmailSetups(): Promise<EmailSetup[]> {
  const { data } = await api.get<EmailSetup[]>("/email-setups");
  return data;
}

export async function createEmailSetup(payload: EmailSetupCreatePayload): Promise<EmailSetup> {
  const { data } = await api.post<EmailSetup>("/email-setups", payload);
  return data;
}

export async function updateEmailSetup(
  emailSetupId: string,
  payload: EmailSetupUpdatePayload
): Promise<EmailSetup> {
  const { data } = await api.patch<EmailSetup>(`/email-setups/${emailSetupId}`, payload);
  return data;
}

export async function deleteEmailSetup(emailSetupId: string): Promise<void> {
  await api.delete(`/email-setups/${emailSetupId}`);
}

export async function importEmailSetupsCsv(file: File): Promise<EmailSetupImportResult> {
  const form = new FormData();
  form.append("file", file);
  // Let the browser set multipart Content-Type with boundary — forcing
  // "multipart/form-data" alone breaks FastAPI file parsing.
  const { data } = await api.post<EmailSetupImportResult>("/email-setups/import", form);
  return data;
}

// ---------------------------------------------------------------------------
// Workspace API keys (singleton provider credentials)
// ---------------------------------------------------------------------------

export interface WorkspaceApiKeys {
  id: string;
  workspace_id: string;
  has_apollo_api_key: boolean;
  has_smartlead_api_key: boolean;
  has_anthropic_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceApiKeysDefaults {
  apollo_api_key: string;
  smartlead_api_key: string;
  anthropic_api_key: string;
}

export interface WorkspaceApiKeysUpsertPayload {
  apollo_api_key?: string | null;
  smartlead_api_key?: string | null;
  anthropic_api_key?: string | null;
}

export async function getWorkspaceApiKeysDefaults(
  workspaceId: string
): Promise<WorkspaceApiKeysDefaults> {
  const { data } = await api.get<WorkspaceApiKeysDefaults>("/workspace-api-keys/defaults", {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function getWorkspaceApiKeys(workspaceId: string): Promise<WorkspaceApiKeys | null> {
  const { data } = await api.get<WorkspaceApiKeys | null>("/workspace-api-keys", {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function upsertWorkspaceApiKeys(
  workspaceId: string,
  payload: WorkspaceApiKeysUpsertPayload
): Promise<WorkspaceApiKeys> {
  const { data } = await api.put<WorkspaceApiKeys>("/workspace-api-keys", payload, {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export function storeSession(auth: AuthTokens) {
  window.localStorage.setItem("access_token", auth.access_token);
  window.localStorage.setItem("refresh_token", auth.refresh_token);
}

export function clearSession() {
  window.localStorage.removeItem("access_token");
  window.localStorage.removeItem("refresh_token");
}

// Revokes both tokens server-side (see backend README §16) before
// clearing them locally — best-effort: a network failure here shouldn't
// block the user from logging out client-side.
export async function logout(): Promise<void> {
  const refreshToken = window.localStorage.getItem("refresh_token");
  try {
    await api.post("/auth/logout", { refresh_token: refreshToken ?? undefined });
  } catch {
    // ignore — still clear the local session below
  } finally {
    clearSession();
  }
}
