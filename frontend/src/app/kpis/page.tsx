"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  adminApi,
  type Employee,
  type KPI,
  type Profile,
  type ProviderPricing,
  type UsageEmployeeProfileRow,
  type UsageEmployeeRow,
  type UsageProfileRow,
  type UsageSummary,
} from "@/lib/api/agentService";
import { useI18n } from "@/lib/i18n";
import { DollarSign, Sparkles, UserRound, Bot, BarChart3, CalendarDays } from "lucide-react";

interface UsageReport {
  pricing: ProviderPricing | null;
  summary: UsageSummary;
  employees: UsageEmployeeRow[];
  profiles: UsageProfileRow[];
  employee_profiles: UsageEmployeeProfileRow[];
  period: {
    year: number;
    month: number;
    start: string;
    end: string;
  };
}

const emptySummary: UsageSummary = {
  runs: 0,
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  total_cost: 0,
};

function currentMonthValue() {
  const now = new Date();
  return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
}

export default function KPIsPage() {
  const { t, safeText } = useI18n();
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [usageReport, setUsageReport] = useState<UsageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState(currentMonthValue());
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");

  const load = async () => {
    setLoading(true);
    const [year, month] = selectedMonth.split("-").map((value) => Number.parseInt(value, 10));
    const params: { year?: number; month?: number; user_id?: string; profile_id?: string } = { year, month };
    if (selectedUserId) params.user_id = selectedUserId;
    if (selectedProfileId) params.profile_id = selectedProfileId;

    const [usageResponse, kpiResponse, employeesResponse, profilesResponse] = await Promise.all([
      adminApi.getUsageReport(params),
      adminApi.getKPIs(),
      adminApi.getEmployees(),
      adminApi.getProfiles(),
    ]);

    setUsageReport(usageResponse.data);
    setKpis(kpiResponse.data.kpis || []);
    setEmployees(employeesResponse.data.employees || []);
    setProfiles(profilesResponse.data.profiles || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const [year, month] = selectedMonth.split("-").map((value) => Number.parseInt(value, 10));
      const params: { year?: number; month?: number; user_id?: string; profile_id?: string } = { year, month };
      if (selectedUserId) params.user_id = selectedUserId;
      if (selectedProfileId) params.profile_id = selectedProfileId;

      const [usageResponse, kpiResponse, employeesResponse, profilesResponse] = await Promise.all([
        adminApi.getUsageReport(params),
        adminApi.getKPIs(),
        adminApi.getEmployees(),
        adminApi.getProfiles(),
      ]);

      if (!cancelled) {
        setUsageReport(usageResponse.data);
        setKpis(kpiResponse.data.kpis || []);
        setEmployees(employeesResponse.data.employees || []);
        setProfiles(profilesResponse.data.profiles || []);
        setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [selectedMonth, selectedProfileId, selectedUserId]);

  const summary = usageReport?.summary || emptySummary;
  const pricing = usageReport?.pricing || null;
  const avgTokensPerRun = summary.runs > 0 ? summary.total_tokens / summary.runs : 0;
  const totalKpiTokens = kpis.reduce((sum, kpi) => sum + (kpi.tokens_used || 0), 0);

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Usage Analytics")}</h1>
        <p className="text-muted-foreground mt-1">{t("Track monthly token and cost consumption by employee and by agent.")}</p>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6 grid gap-4 md:grid-cols-4">
          <div className="space-y-2">
            <Label>{t("Month")}</Label>
            <Input type="month" value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} className="kos-input" />
          </div>
          <div className="space-y-2">
            <Label>{t("Employee")}</Label>
            <select className="w-full p-2 border rounded-xl text-sm kos-input" value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)}>
              <option value="">{t("All employees")}</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name || employee.email}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>{t("Agent / Profile")}</Label>
            <select className="w-full p-2 border rounded-xl text-sm kos-input" value={selectedProfileId} onChange={(event) => setSelectedProfileId(event.target.value)}>
              <option value="">{t("All agents")}</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {safeText(profile.name)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={() => void load()} className="kos-gradient-btn text-white px-6 py-2 rounded-xl font-medium w-full">
              {t("Apply Filters")}
            </button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <Card className="kos-card">
          <div className="card-gradient-top" />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("Monthly Cost")}</CardTitle>
            <DollarSign className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${summary.total_cost.toFixed(4)}</div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #F59E0B, #D97706)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("Total Tokens")}</CardTitle>
            <Sparkles className="h-4 w-4 text-amber-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.total_tokens.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #3B82F6, #2563EB)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("Runs")}</CardTitle>
            <BarChart3 className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.runs.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground mt-1">{avgTokensPerRun.toFixed(0)} {t("avg tokens/run")}</p>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #8B5CF6, #7C3AED)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("Active Pricing")}</CardTitle>
            <CalendarDays className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">{pricing ? `$${pricing.monthly_price_usd} / ${pricing.monthly_token_allowance.toLocaleString()} tok` : t("Not set")}</div>
            <p className="text-xs text-muted-foreground mt-1">{pricing ? `${pricing.usd_per_1m_tokens.toFixed(4)} USD / 1M tok` : `${totalKpiTokens.toLocaleString()} ${t("KPI tokens tracked")}`}</p>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <div className="card-gradient-top" />
        <CardHeader>
          <CardTitle>{t("Employee Consumption This Month")}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3 font-medium">{t("Employee")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Runs")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Input Tokens")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Output Tokens")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Total Tokens")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Cost")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(usageReport?.employees || []).map((row) => (
                    <tr key={row.user_id} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
                      <td className="py-2 px-3">
                        <div className="font-medium">{row.full_name || row.email}</div>
                        <div className="text-xs text-muted-foreground">{row.email}</div>
                      </td>
                      <td className="py-2 px-3">{row.runs}</td>
                      <td className="py-2 px-3">{row.input_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3">{row.output_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3 font-semibold">{row.total_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3 text-emerald-700 font-semibold">${row.total_cost.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="kos-card">
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #0F766E, #0EA5A4)" }} />
        <CardHeader>
          <CardTitle>{t("Agent Consumption This Month")}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3 font-medium">{t("Agent")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Runs")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Input Tokens")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Output Tokens")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Total Tokens")}</th>
                    <th className="text-left py-2 px-3 font-medium">{t("Cost")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(usageReport?.profiles || []).map((row) => (
                    <tr key={row.profile_id || "unassigned"} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
                      <td className="py-2 px-3">
                        <div className="font-medium">{safeText(row.profile_name)}</div>
                        <div className="text-xs text-muted-foreground">{safeText(row.profile_slug || t("unassigned"))}</div>
                      </td>
                      <td className="py-2 px-3">{row.runs}</td>
                      <td className="py-2 px-3">{row.input_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3">{row.output_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3 font-semibold">{row.total_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3 text-emerald-700 font-semibold">${row.total_cost.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="kos-card">
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #6366F1, #4F46E5)" }} />
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserRound className="h-4 w-4 text-indigo-600" />
            {t("Employee x Agent Matrix")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {(usageReport?.employee_profiles || []).map((row) => (
                <Card key={`${row.user_id}-${row.profile_id || "unassigned"}`} className="border border-gray-100 shadow-none">
                  <CardContent className="pt-4 space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{row.full_name || row.email}</p>
                        <p className="text-xs text-muted-foreground">{row.email}</p>
                      </div>
                      <Badge variant="outline">
                        <Bot className="mr-1 h-3 w-3" />
                        {safeText(row.profile_name)}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>{t("Runs")}: <span className="font-semibold">{row.runs}</span></div>
                      <div>{t("Total Tokens")}: <span className="font-semibold">{row.total_tokens.toLocaleString()}</span></div>
                      <div>{t("Input")}: <span className="font-semibold">{row.input_tokens.toLocaleString()}</span></div>
                      <div>{t("Output")}: <span className="font-semibold">{row.output_tokens.toLocaleString()}</span></div>
                    </div>
                    <div className="text-emerald-700 font-semibold">${row.total_cost.toFixed(4)}</div>
                  </CardContent>
                </Card>
              ))}
              {(usageReport?.employee_profiles || []).length === 0 && (
                <p className="text-muted-foreground text-sm italic text-center py-4 md:col-span-2">No monthly usage rows yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
