"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Download, Play, RotateCw, Square, Wrench, ServerCog, Terminal } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api/client";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";

interface HermesStatus {
  installed?: boolean;
  running?: boolean;
  status?: string;
  docker_image?: string | null;
  version?: string | null;
  last_sync_status?: string | null;
  queue_health?: string;
  run_health?: string;
  message?: string;
  failed_profile_syncs?: number;
}

export default function HermesRuntimePage() {
  const { t } = useI18n();
  const [status, setStatus] = useState<HermesStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const load = async () => {
    const [statusRes, logsRes] = await Promise.all([
      apiClient.get("/admin/hermes/status"),
      apiClient.get("/admin/hermes/logs", { params: { limit: 200 } }),
    ]);
    setStatus(statusRes.data || {});
    setLogs(logsRes.data.logs || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        const [statusRes, logsRes] = await Promise.all([
          apiClient.get("/admin/hermes/status"),
          apiClient.get("/admin/hermes/logs", { params: { limit: 200 } }),
        ]);
        if (!cancelled) {
          setStatus(statusRes.data || {});
          setLogs(logsRes.data.logs || []);
          setLoading(false);
        }
      } catch (error: unknown) {
        if (!cancelled) {
          toast.error(getErrorMessage(error, "Failed to load Hermes runtime status"));
          setLoading(false);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  const runAction = async (action: "install" | "start" | "restart" | "stop" | "repair-sync") => {
    setBusyAction(action);
    try {
      await apiClient.post(`/admin/hermes/${action}`);
      toast.success(`Hermes ${action} requested`);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, `Hermes ${action} failed`));
    } finally {
      setBusyAction(null);
    }
  };

  const statusLabel = status?.status || (status?.running ? "running" : "unknown");
  const isHealthy = statusLabel === "running" || status?.running;

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Hermes Runtime")}</h1>
          <p className="text-muted-foreground mt-1">{t("Install, health-check, restart, and repair the Hermes execution layer.")}</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t("Check Health")}
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card className="kos-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Runtime")}</p>
                <p className="text-2xl font-bold capitalize">{t(statusLabel.replaceAll("_", " "))}</p>
              </div>
              <ServerCog className={isHealthy ? "h-8 w-8 text-emerald-600" : "h-8 w-8 text-amber-600"} />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{t("Installed")}</p>
            <Badge className={status?.installed ? "kos-badge-green mt-2" : "kos-badge-gray mt-2"}>
              {status?.installed ? t("Installed") : t("Not installed")}
            </Badge>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{t("Version")}</p>
            <p className="text-xl font-semibold mt-1">{status?.version || t("Unknown")}</p>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{t("Failed Syncs")}</p>
            <p className="text-2xl font-bold text-red-600 mt-1">{status?.failed_profile_syncs ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <CardHeader>
          <CardTitle>{t("Lifecycle Controls")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button onClick={() => void runAction("install")} disabled={!!busyAction}>
            <Download className="mr-2 h-4 w-4" />
            {t("Install")}
          </Button>
          <Button variant="outline" onClick={() => void runAction("start")} disabled={!!busyAction}>
            <Play className="mr-2 h-4 w-4" />
            {t("Start")}
          </Button>
          <Button variant="outline" onClick={() => void runAction("restart")} disabled={!!busyAction}>
            <RotateCw className="mr-2 h-4 w-4" />
            {t("Restart")}
          </Button>
          <Button variant="outline" onClick={() => void runAction("stop")} disabled={!!busyAction}>
            <Square className="mr-2 h-4 w-4" />
            {t("Stop")}
          </Button>
          <Button variant="outline" onClick={() => void runAction("repair-sync")} disabled={!!busyAction}>
            <Wrench className="mr-2 h-4 w-4" />
            {t("Repair Sync")}
          </Button>
        </CardContent>
      </Card>

      <Card className="kos-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            {t("Runtime Details")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="grid gap-3 md:grid-cols-2">
            <div><span className="text-muted-foreground">{t("Docker image:")}</span> {status?.docker_image || t("Not reported")}</div>
            <div><span className="text-muted-foreground">{t("Queue health:")}</span> {status?.queue_health || t("Unknown")}</div>
            <div><span className="text-muted-foreground">{t("Run health:")}</span> {status?.run_health || t("Unknown")}</div>
            <div><span className="text-muted-foreground">{t("Last sync:")}</span> {status?.last_sync_status || t("Unknown")}</div>
          </div>
          {status?.message && <p className="text-amber-700 bg-amber-50 border border-amber-100 rounded-md p-3">{status.message}</p>}
          <pre className="bg-gray-950 text-gray-100 rounded-md p-4 overflow-auto max-h-80 text-xs">
            {logs.length ? logs.join("\n") : t("No logs available.")}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
