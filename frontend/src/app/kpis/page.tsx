"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminApi, type KPI } from "@/lib/api/agentService";
import { BarChart3, MessageSquare, Clock, Target, Sparkles, TrendingUp } from "lucide-react";

export default function KPIsPage() {
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterUserId, setFilterUserId] = useState("");
  const [filterDate, setFilterDate] = useState("");

  const load = async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filterUserId) params.user_id = filterUserId;
    if (filterDate) params.date = filterDate;
    const response = await adminApi.getKPIs(params);
    setKpis(response.data.kpis || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const params: Record<string, string> = {};
      if (filterUserId) params.user_id = filterUserId;
      if (filterDate) params.date = filterDate;
      const response = await adminApi.getKPIs(params);
      if (!cancelled) {
        setKpis(response.data.kpis || []);
        setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [filterDate, filterUserId]);

  const totalMessages = kpis.reduce((sum, kpi) => sum + kpi.messages_sent, 0);
  const totalTasks = kpis.reduce((sum, kpi) => sum + kpi.tasks_completed, 0);
  const totalMinutes = kpis.reduce((sum, kpi) => sum + kpi.active_minutes, 0);
  const totalTokens = kpis.reduce((sum, kpi) => sum + (kpi.tokens_used || 0), 0);
  const avgQuality = kpis.length > 0
    ? (kpis.filter((kpi) => kpi.avg_response_quality !== null).reduce((sum, kpi) => sum + (kpi.avg_response_quality || 0), 0) / kpis.length).toFixed(1)
    : "—";

  const maxBar = Math.max(...kpis.map((kpi) => kpi.messages_sent), 1);

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">KPIs</h1>
        <p className="text-muted-foreground mt-1">Review employee activity, throughput, and token usage.</p>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6 flex gap-4">
          <div className="space-y-2 flex-1">
            <Label>User ID</Label>
            <Input value={filterUserId} onChange={(event) => setFilterUserId(event.target.value)} className="kos-input" />
          </div>
          <div className="space-y-2 flex-1">
            <Label>Date</Label>
            <Input type="date" value={filterDate} onChange={(event) => setFilterDate(event.target.value)} className="kos-input" />
          </div>
          <div className="flex items-end">
            <button onClick={() => void load()} className="kos-gradient-btn text-white px-6 py-2 rounded-xl font-medium">
              Apply
            </button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-5">
        <Card className="kos-card">
          <div className="card-gradient-top" />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Messages</CardTitle>
            <MessageSquare className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalMessages.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tasks</CardTitle>
            <Target className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalTasks.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #8B5CF6, #7C3AED)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Minutes</CardTitle>
            <Clock className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalMinutes.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #F59E0B, #D97706)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tokens</CardTitle>
            <Sparkles className="h-4 w-4 text-amber-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalTokens.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #EC4899, #DB2777)" }} />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Quality</CardTitle>
            <TrendingUp className="h-4 w-4 text-pink-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgQuality}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <div className="card-gradient-top" />
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-indigo-600" />
            Messages Per User
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="space-y-3">
              {kpis.map((kpi) => (
                <div key={`${kpi.user_id}-${kpi.date}`} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-mono truncate max-w-[200px]">{kpi.user_id}</span>
                    <span className="text-muted-foreground">{kpi.messages_sent.toLocaleString()} messages</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-4 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full transition-all duration-500"
                      style={{ width: `${(kpi.messages_sent / maxBar) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
              {kpis.length === 0 && (
                <p className="text-muted-foreground text-sm italic text-center py-4">No KPI data yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="kos-card">
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3 font-medium">User</th>
                  <th className="text-left py-2 px-3 font-medium">Date</th>
                  <th className="text-left py-2 px-3 font-medium">Messages</th>
                  <th className="text-left py-2 px-3 font-medium">Tasks</th>
                  <th className="text-left py-2 px-3 font-medium">Minutes</th>
                  <th className="text-left py-2 px-3 font-medium">Tokens</th>
                  <th className="text-left py-2 px-3 font-medium">Quality</th>
                  <th className="text-left py-2 px-3 font-medium">Tools</th>
                </tr>
              </thead>
              <tbody>
                {kpis.map((kpi) => (
                  <tr key={`${kpi.user_id}-${kpi.date}-row`} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
                    <td className="py-2 px-3 font-mono text-xs truncate max-w-[120px]">{kpi.user_id}</td>
                    <td className="py-2 px-3">{kpi.date}</td>
                    <td className="py-2 px-3 font-medium">{kpi.messages_sent}</td>
                    <td className="py-2 px-3">{kpi.tasks_completed}</td>
                    <td className="py-2 px-3">{kpi.active_minutes}</td>
                    <td className="py-2 px-3">{kpi.tokens_used?.toLocaleString() || 0}</td>
                    <td className="py-2 px-3">{kpi.avg_response_quality || "—"}</td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1">
                        {(kpi.tools_used || []).slice(0, 3).map((tool) => (
                          <Badge key={tool} variant="outline" className="text-xs">
                            {tool}
                          </Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
                {kpis.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-muted-foreground">No KPI rows yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
