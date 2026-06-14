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
  is_active: boolean;
  agents_md?: string;
  agents_md_preview: string;
  system_prompt?: string;
  created_at: string;
}

export interface ProfileAssignment {
  id: string;
  user_id: string;
  profile_id: string;
  priority: number;
  user_email: string | null;
  profile_name: string | null;
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
  user_id: string;
  provider: string;
  key_prefix: string;
  is_active: boolean;
  daily_budget: number;
  spent_today: number;
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
    apiClient.delete(`/admin/employees/${userId}`),

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

  createApiKey: (data: { user_id: string; provider: string; api_key: string; daily_budget?: number }) =>
    apiClient.post("/admin/api-keys", data),

  updateApiKey: (keyId: string, data: { is_active?: boolean; daily_budget?: number; api_key?: string }) =>
    apiClient.put(`/admin/api-keys/${keyId}`, data),

  deleteApiKey: (keyId: string) =>
    apiClient.delete(`/admin/api-keys/${keyId}`),
};

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post("/auth/login", { email, password }),

  register: (data: { email: string; password: string; full_name?: string; department?: string }) =>
    apiClient.post("/auth/register", data),

  me: () =>
    apiClient.get("/auth/me"),
};

export const healthApi = {
  health: () => apiClient.get("/health"),
  status: () => apiClient.get("/status"),
};
