import apiClient from "./client";

export interface Employee {
  id: string;
  email: string;
  full_name: string | null;
  department: string | null;
  role: string;
  is_active: boolean;
  is_activated?: boolean;
  has_invite_token?: boolean;
  max_tokens_per_day: number;
  max_requests_per_day: number;
  created_at: string;
}

export interface EmployeeCreatePayload {
  email: string;
  full_name: string;
  department?: string;
  role: string;
  max_tokens_per_day: number;
  max_requests_per_day: number;
}

export interface EmployeeUpdatePayload {
  full_name?: string;
  department?: string;
  role?: string;
  is_active?: boolean;
  max_tokens_per_day?: number;
  max_requests_per_day?: number;
}

export interface KPI {
  user_id: string;
  date: string;
  tasks_completed: number;
  messages_sent: number;
  tokens_used: number;
  avg_response_quality: number | null;
  active_minutes: number;
  tools_used: string[];
}

export interface ProviderPricing {
  id?: string;
  provider: string;
  currency: string;
  monthly_price_usd: number;
  monthly_token_allowance: number;
  is_active?: boolean;
  usd_per_1m_tokens: number;
  created_at?: string;
  updated_at?: string;
}

export interface UsageSummary {
  runs: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: number;
}

export interface UsageEmployeeRow extends UsageSummary {
  user_id: string;
  email: string;
  full_name: string | null;
}

export interface UsageProfileRow extends UsageSummary {
  profile_id: string | null;
  profile_name: string;
  profile_slug: string | null;
}

export interface UsageEmployeeProfileRow extends UsageSummary {
  user_id: string;
  email: string;
  full_name: string | null;
  profile_id: string | null;
  profile_name: string;
  profile_slug: string | null;
}

export interface AlertItem {
  id: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  message: string;
  context: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  last_notified_at: string | null;
  is_acknowledged: boolean;
  created_at: string;
}

export interface AuditLog {
  id: number;
  user_id: string | null;
  action: string;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface AgentTool {
  name?: string;
  [key: string]: unknown;
}

export interface AgentTemplate {
  name: string;
  department: string | null;
  model_name: string;
  tools: Array<string | AgentTool>;
  temperature: number;
}

export interface Profile {
  id: string;
  name: string;
  slug: string;
  soul_md: string | null;
  skills: string[];
  skill_details?: SkillDefinition[];
  is_active: boolean;
  agents_md?: string;
  agents_md_preview: string;
  system_prompt?: string;
  runtime_type?: "hermes" | "direct_llm";
  hermes_profile_id?: string | null;
  hermes_workspace_path?: string | null;
  hermes_sync_status?: string;
  hermes_sync_error?: string | null;
  version?: number;
  last_synced_at?: string | null;
  provider_key_id?: string | null;
  max_tokens_per_day?: number | null;
  max_requests_per_day?: number | null;
  daily_cost_budget?: number | null;
  allowed_providers?: string[];
  allowed_mcp_servers?: string[];
  allowed_tools?: string[];
  approval_required_tools?: string[];
  memory_settings?: Record<string, unknown>;
  created_at: string;
}

export interface SkillDefinition {
  id: string;
  name: string;
  slug: string;
  description: string;
  instructions_md: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProfileAssignment {
  id: string;
  user_id: string;
  profile_id: string;
  priority: number;
  user_email: string | null;
  profile_name: string | null;
  profile_runtime_type?: string;
  profile_sync_status?: string;
  profile_version?: number;
  profile_provider_key_id?: string | null;
}

export interface Session {
  id: string;
  user_id: string;
  title: string | null;
  profile_name: string | null;
  created_at: string;
}

export interface UserApiKey {
  id: string;
  owner_type: "user" | "profile" | "platform";
  user_id: string | null;
  profile_id: string | null;
  profile_ids?: string[];
  profile_names?: string[];
  provider: string;
  key_prefix: string;
  is_active: boolean;
  daily_budget: number;
  spent_today: number;
}

export interface AdminAgentTestResponse {
  conversation_id: string | null;
  message_id: string | null;
  content: string;
  tokens_used: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number | null;
  model: string | null;
  provider: string | null;
  runtime_type: string | null;
  request_url: string | null;
  upstream_target: string | null;
  profile_name: string | null;
  profile_id: string | null;
  total_cost: number | null;
  pricing_snapshot: Record<string, unknown> | null;
}

export const adminApi = {
  // Employees
  getEmployees: (params?: Record<string, string>) =>
    apiClient.get("/admin/employees", { params }),

  createEmployee: (data: EmployeeCreatePayload) =>
    apiClient.post("/admin/employees", data),

  updateEmployee: (userId: string, data: EmployeeUpdatePayload) =>
    apiClient.put(`/admin/employees/${userId}`, data),

  disableEmployee: (userId: string) =>
    apiClient.put(`/admin/employees/${userId}`, { is_active: false }),

  deleteEmployee: (userId: string) =>
    apiClient.delete(`/admin/employees/${userId}`),

  createDesktopInvite: (userId: string) =>
    apiClient.post(`/admin/employees/${userId}/desktop-invite`),

  updateQuotas: (userId: string, data: { max_tokens_per_day: number; max_requests_per_day: number }) =>
    apiClient.put(`/admin/employees/${userId}/quotas`, data),

  // KPIs
  getKPIs: (params?: Record<string, string>) =>
    apiClient.get("/admin/kpis", { params }),

  // Audit
  getAuditLog: (params?: Record<string, string>) =>
    apiClient.get("/admin/audit-log", { params }),

  // Templates
  getTemplates: () =>
    apiClient.get("/admin/agent-templates"),

  // Profiles
  getProfiles: () =>
    apiClient.get("/admin/profiles"),

  // Skills
  getSkills: (params?: { include_inactive?: boolean }) =>
    apiClient.get("/admin/skills", { params }),

  createSkill: (data: Partial<SkillDefinition>) =>
    apiClient.post("/admin/skills", data),

  updateSkill: (skillId: string, data: Partial<SkillDefinition>) =>
    apiClient.put(`/admin/skills/${skillId}`, data),

  deleteSkill: (skillId: string) =>
    apiClient.delete(`/admin/skills/${skillId}`),

  createProfile: (data: Partial<Profile>) =>
    apiClient.post("/admin/profiles", data),

  updateProfile: (profileId: string, data: Partial<Profile>) =>
    apiClient.put(`/admin/profiles/${profileId}`, data),

  deleteProfile: (profileId: string) =>
    apiClient.delete(`/admin/profiles/${profileId}`),

  // Assignments
  getAssignments: () =>
    apiClient.get("/admin/assignments"),

  assignProfile: (data: { user_id: string; profile_id: string; priority?: number }) =>
    apiClient.post("/admin/assignments", data),

  removeAssignment: (assignmentId: string) =>
    apiClient.delete(`/admin/assignments/${assignmentId}`),

  // Sessions
  getSessions: (params?: { user_id?: string; profile_name?: string; date_from?: string; date_to?: string; limit?: number }) =>
    apiClient.get("/admin/sessions", { params }),

  getSessionMessages: (sessionId: string) =>
    apiClient.get(`/admin/sessions/${sessionId}`),

  // API Keys
  getApiKeys: () =>
    apiClient.get("/admin/api-keys"),

  getProviderPricing: (params?: Record<string, string>) =>
    apiClient.get("/admin/provider-pricing", { params }),

  updateProviderPricing: (
    provider: string,
    data: { monthly_price_usd: number; monthly_token_allowance: number; currency?: string }
  ) => apiClient.put(`/admin/provider-pricing/${provider}`, data),

  getUsageReport: (params?: { year?: number; month?: number; user_id?: string; profile_id?: string }) =>
    apiClient.get("/admin/usage-report", { params }),

  getAlerts: (params?: { status?: string; severity?: string; limit?: number }) =>
    apiClient.get("/admin/monitoring/alerts", { params }),

  runAlertEvaluation: () =>
    apiClient.post("/admin/monitoring/alerts/run"),

  acknowledgeAlert: (alertId: string) =>
    apiClient.post(`/admin/monitoring/alerts/${alertId}/ack`),

  createApiKey: (data: {
    owner_type: "user" | "profile" | "platform";
    user_id?: string | null;
    profile_id?: string | null;
    provider: string;
    api_key: string;
    daily_budget?: number;
  }) =>
    apiClient.post("/admin/api-keys", data),

  updateApiKey: (keyId: string, data: { is_active?: boolean; daily_budget?: number; api_key?: string }) =>
    apiClient.put(`/admin/api-keys/${keyId}`, data),

  deleteApiKey: (keyId: string) =>
    apiClient.delete(`/admin/api-keys/${keyId}`),

  // Hermes runtime
  getHermesStatus: () =>
    apiClient.get("/admin/hermes/status"),

  hermesAction: (action: "install" | "start" | "restart" | "stop" | "repair-sync") =>
    apiClient.post(`/admin/hermes/${action}`),

  getHermesLogs: (limit = 200) =>
    apiClient.get("/admin/hermes/logs", { params: { limit } }),

  testAgentMessage: (data: {
    message: string;
    profile_name: string;
    conversation_id?: string | null;
    agent_template_name?: string;
    project_context?: string;
  }) => apiClient.post<AdminAgentTestResponse>("/admin/agent-test/message", data),
};

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post("/auth/login", { email, password }),

  logout: () =>
    apiClient.post("/auth/logout"),

  register: (data: { email: string; password: string; full_name?: string; department?: string }) =>
    apiClient.post("/auth/register", data),

  me: () =>
    apiClient.get("/auth/me"),
};

export const healthApi = {
  health: () => apiClient.get("/health"),
  status: () => apiClient.get("/status"),
};
