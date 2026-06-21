"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  MessageSquare,
  Activity,
  Zap,
  Clock,
  BarChart3,
  UserCheck,
  Sparkles,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import apiClient from "@/lib/api/client";
import { adminApi, type AlertItem } from "@/lib/api/agentService";

interface DashboardStats {
  summary: {
    total_employees: number;
    active_employees: number;
    online_now: number;
    messages_today: number;
    messages_yesterday: number;
    messages_change_pct: number;
    sessions_today: number;
    total_sessions: number;
    tokens_today: number;
    week_messages: number;
  };
  top_users: Array<{
    id: string;
    email: string;
    full_name: string | null;
    messages_sent: number;
    tokens_used: number;
  }>;
  activity_counts: Record<string, number>;
  messages_per_day: Array<{ date: string; messages: number }>;
  tokens_per_day: Array<{ date: string; tokens: number }>;
}

interface ActivityItem {
  id: number;
  user_id: string;
  user_email: string;
  user_name: string;
  action: string;
  details: Record<string, string | number | boolean | null | undefined>;
  session_id: string | null;
  created_at: string;
}

interface OnlineUser {
  id: string;
  email: string;
  full_name: string | null;
  department: string | null;
  role: string;
  last_seen: string | null;
}

const statColors = [
  { gradient: "from-blue-500 to-blue-600" },
  { gradient: "from-emerald-500 to-emerald-600" },
  { gradient: "from-purple-500 to-purple-600" },
  { gradient: "from-amber-500 to-amber-600" },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        const [statsRes, onlineRes, activitiesRes, alertsRes] = await Promise.all([
          apiClient.get("/admin/monitoring/dashboard-stats"),
          apiClient.get("/admin/monitoring/online-users"),
          apiClient.get("/admin/monitoring/activity-feed?limit=50"),
          adminApi.getAlerts({ status: "active", limit: 20 }),
        ]);

        if (mounted) {
          setStats(statsRes.data);
          setOnlineUsers(onlineRes.data.online_users || []);
          setActivities(activitiesRes.data.activities || []);
          setAlerts(alertsRes.data.alerts || []);
        }
      } catch {
        // Keep dashboard resilient when backend data is incomplete.
      }
    };

    void load();
    const interval = setInterval(() => {
      void load();
    }, 15000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const summary = stats?.summary || {
    total_employees: 0,
    active_employees: 0,
    online_now: 0,
    messages_today: 0,
    messages_yesterday: 0,
    messages_change_pct: 0,
    sessions_today: 0,
    total_sessions: 0,
    tokens_today: 0,
    week_messages: 0,
  };

  const maxMessages = Math.max(...(stats?.messages_per_day.map((day) => day.messages) || [1]), 1);
  const maxTokens = Math.max(...(stats?.tokens_per_day.map((day) => day.tokens) || [1]), 1);

  const actionLabel = (action: string) => {
    switch (action) {
      case "ws_connected":
        return "Connected";
      case "ws_disconnected":
        return "Disconnected";
      case "message_sent":
        return "Sent message";
      case "login":
        return "Logged in";
      case "account_activated":
        return "Activated account";
      default:
        return action;
    }
  };

  const formatTime = (iso: string) =>
    new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

  const statData = [
    {
      title: "Employees",
      value: summary.total_employees,
      description: `${summary.active_employees} active`,
      icon: Users,
      gradient: statColors[0].gradient,
    },
    {
      title: "Online Now",
      value: summary.online_now,
      description: "Desktop app currently connected",
      icon: Zap,
      gradient: statColors[1].gradient,
    },
    {
      title: "Messages Today",
      value: summary.messages_today.toLocaleString(),
      description: `${Math.abs(summary.messages_change_pct)}% vs yesterday`,
      trend: summary.messages_change_pct,
      icon: MessageSquare,
      gradient: statColors[2].gradient,
    },
    {
      title: "Tokens Today",
      value: summary.tokens_today.toLocaleString(),
      description: `${summary.sessions_today} sessions today`,
      icon: Sparkles,
      gradient: statColors[3].gradient,
    },
  ];

  return (
    <div className="p-8 space-y-8 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Operational status for employees, sessions, and usage.</p>
        </div>
        <Badge variant={summary.online_now > 0 ? "default" : "secondary"} className="text-sm px-4 py-1.5 bg-gradient-to-r from-emerald-500 to-teal-500 text-white border-0">
          <UserCheck className="h-3 w-3 mr-1" />
          {summary.online_now} online
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statData.map((stat) => (
          <Card key={stat.title} className="kos-card">
            <div className="card-gradient-top" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.gradient} flex items-center justify-center text-white shadow-lg`}>
                <stat.icon className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                {stat.trend !== undefined ? (
                  <>
                    {stat.trend >= 0 ? (
                      <ArrowUp className="h-3 w-3 text-green-500" />
                    ) : (
                      <ArrowDown className="h-3 w-3 text-red-500" />
                    )}
                    <span className="font-medium">{stat.description}</span>
                  </>
                ) : (
                  stat.description
                )}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #6366F1, #818CF8)" }} />
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-indigo-600" />
              Messages, last 7 days
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats?.messages_per_day.map((day) => (
                <div key={day.date} className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground w-20 font-medium">{day.date}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full flex items-center justify-end pr-2 transition-all duration-500"
                      style={{ width: `${Math.max((day.messages / maxMessages) * 100, 2)}%` }}
                    >
                      <span className="text-xs text-white font-bold">{day.messages}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #F59E0B, #D97706)" }} />
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-600" />
              Tokens, last 7 days
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats?.tokens_per_day.map((day) => (
                <div key={day.date} className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground w-20 font-medium">{day.date}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-amber-600 rounded-full flex items-center justify-end pr-2 transition-all duration-500"
                      style={{ width: `${Math.max((day.tokens / maxTokens) * 100, 2)}%` }}
                    >
                      <span className="text-xs text-white font-bold">{day.tokens.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {stats?.activity_counts && Object.keys(stats.activity_counts).length > 0 && (
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-600" />
              Activity counts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.activity_counts).map(([action, count]) => (
                <Badge key={action} className="kos-badge kos-badge-blue text-sm px-3 py-1.5">
                  {actionLabel(action)}: <span className="font-bold ml-1">{count}</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #3B82F6, #2563EB)" }} />
          <CardHeader>
            <CardTitle>Top users today</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.top_users && stats.top_users.length > 0 ? (
              <div className="space-y-3">
                {stats.top_users.map((user, index) => (
                  <div key={user.id} className="flex items-center justify-between p-3 rounded-xl border border-gray-100 bg-gray-50 kos-animate-in" style={{ animationDelay: `${index * 50}ms` }}>
                    <div>
                      <p className="text-sm font-semibold">{user.full_name || user.email}</p>
                      <p className="text-xs text-muted-foreground">{user.email}</p>
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-bold text-indigo-600">{user.messages_sent} messages</p>
                      <p className="text-xs text-muted-foreground">{user.tokens_used.toLocaleString()} tokens</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm italic text-center py-4">No activity yet.</p>
            )}
          </CardContent>
        </Card>

        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-emerald-500" />
              Online users ({onlineUsers.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {onlineUsers.length > 0 ? (
              <div className="space-y-3">
                {onlineUsers.map((user) => (
                  <div key={user.id} className="flex items-center justify-between p-3 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-100 kos-animate-in">
                    <div className="flex items-center gap-3">
                      <div className="w-3 h-3 rounded-full bg-emerald-500 kos-online-pulse" />
                      <div>
                        <p className="text-sm font-semibold">{user.full_name || user.email}</p>
                        <p className="text-xs text-muted-foreground">{user.email}</p>
                      </div>
                    </div>
                    <Badge variant="outline" className="bg-white">{user.department || "—"}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm italic text-center py-4">Nobody online right now.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #EF4444, #DC2626)" }} />
        <CardHeader>
          <CardTitle>Active Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length > 0 ? (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div key={alert.id} className="flex items-start justify-between gap-4 p-3 rounded-xl border border-red-100 bg-red-50/40">
                  <div>
                    <p className="font-semibold">{alert.title}</p>
                    <p className="text-sm text-muted-foreground">{alert.message}</p>
                  </div>
                  <Badge variant="outline" className={alert.severity === "critical" ? "border-red-400 text-red-700" : "border-amber-400 text-amber-700"}>
                    {alert.severity}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm italic text-center py-4">No active alerts.</p>
          )}
        </CardContent>
      </Card>

      <Card className="kos-card">
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #6366F1, #4F46E5)" }} />
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-indigo-600" />
            Recent activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {activities.length > 0 ? (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {activities.map((activity, index) => (
                <div key={activity.id} className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-indigo-200 hover:bg-indigo-50/50 transition-all kos-animate-in" style={{ animationDelay: `${index * 30}ms` }}>
                  <div>
                    <p className="font-medium">{activity.user_name}</p>
                    <p className="text-xs text-muted-foreground">{actionLabel(activity.action)}</p>
                  </div>
                  <div className="text-left">
                    <p className="text-xs text-muted-foreground">{formatTime(activity.created_at)}</p>
                    {typeof activity.details.tokens_used === "number" && (
                      <p className="text-xs font-medium text-indigo-600">{activity.details.tokens_used} tokens</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm italic text-center py-4">No recent activity.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
