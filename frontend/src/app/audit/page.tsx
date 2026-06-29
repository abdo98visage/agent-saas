"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminApi, type AuditLog } from "@/lib/api/agentService";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";
import { formatRiyadhDateTime } from "@/lib/time";
import { Shield, Search, Filter } from "lucide-react";
import { toast } from "sonner";

export default function AuditPage() {
  const { t, safeText } = useI18n();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        const response = await adminApi.getAuditLog({ limit: "200" });
        if (!cancelled) {
          setLogs(response.data.audit_log || []);
          setLoading(false);
        }
      } catch (error: unknown) {
        if (!cancelled) {
          toast.error(getErrorMessage(error, "Failed to load audit log"));
          setLoading(false);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  const actionColor = (action: string) => {
    if (action.includes("add")) return "kos-badge-green";
    if (action.includes("disable")) return "kos-badge-red";
    if (action.includes("update")) return "kos-badge-blue";
    if (action.includes("set_limits")) return "kos-badge-amber";
    return "kos-badge-gray";
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Audit Log")}</h1>
        <p className="text-muted-foreground mt-1">{t("Track privileged actions and changes across the platform.")}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card className="kos-card">
          <div className="card-gradient-top" />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Total")}</p>
                <p className="text-2xl font-bold">{logs.length}</p>
              </div>
              <Shield className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Adds")}</p>
                <p className="text-2xl font-bold text-emerald-600">{logs.filter((log) => log.action.includes("add")).length}</p>
              </div>
              <Filter className="h-8 w-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #3B82F6, #2563EB)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Updates")}</p>
                <p className="text-2xl font-bold text-blue-600">{logs.filter((log) => log.action.includes("update")).length}</p>
              </div>
              <Search className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #EF4444, #DC2626)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Disables")}</p>
                <p className="text-2xl font-bold text-red-600">{logs.filter((log) => log.action.includes("disable")).length}</p>
              </div>
              <Shield className="h-8 w-8 text-red-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Action")}</TableHead>
                  <TableHead>{t("User")}</TableHead>
                  <TableHead>{t("IP")}</TableHead>
                  <TableHead>{t("Details")}</TableHead>
                  <TableHead className="text-right">{t("Created")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell><Badge className={actionColor(log.action)}>{safeText(log.action)}</Badge></TableCell>
                    <TableCell className="text-sm">{log.user_id || "—"}</TableCell>
                    <TableCell className="text-sm font-mono text-xs">{log.ip_address || "—"}</TableCell>
                    <TableCell className="text-xs max-w-xs truncate">{safeText(JSON.stringify(log.details))}</TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">{formatRiyadhDateTime(log.created_at)}</TableCell>
                  </TableRow>
                ))}
                {logs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">No audit events yet.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
