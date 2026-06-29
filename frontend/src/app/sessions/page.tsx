"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { MessageSquare, Eye, Filter } from "lucide-react";
import apiClient from "@/lib/api/client";
import { useI18n } from "@/lib/i18n";
import { formatRiyadhDateKey, formatRiyadhDateTime } from "@/lib/time";

interface Session {
  id: string;
  user_id: string;
  title: string | null;
  profile_name: string | null;
  created_at: string;
}

interface SessionMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

interface SessionDetail {
  session_id: string;
  messages: SessionMessage[];
  count: number;
}

export default function SessionsPage() {
  const { t, safeText } = useI18n();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [filterUserId, setFilterUserId] = useState("");
  const [filterProfile, setFilterProfile] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");

  const load = async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filterUserId) params.user_id = filterUserId;
    if (filterProfile) params.profile_name = filterProfile;
    if (filterDateFrom) params.date_from = filterDateFrom;
    const response = await apiClient.get("/admin/sessions", { params });
    setSessions(response.data.sessions || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const params: Record<string, string> = {};
      if (filterUserId) params.user_id = filterUserId;
      if (filterProfile) params.profile_name = filterProfile;
      if (filterDateFrom) params.date_from = filterDateFrom;
      const response = await apiClient.get("/admin/sessions", { params });
      if (!cancelled) {
        setSessions(response.data.sessions || []);
        setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [filterDateFrom, filterProfile, filterUserId]);

  const viewSession = async (sessionId: string) => {
    const response = await apiClient.get(`/admin/sessions/${sessionId}`);
    setSelectedSession(response.data);
  };

  const today = formatRiyadhDateKey(new Date());

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Sessions")}</h1>
        <p className="text-muted-foreground mt-1">{t("Inspect conversation history by user, profile, and date.")}</p>
      </div>

      <Card className="kos-card">
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #3B82F6, #2563EB)" }} />
        <CardContent className="pt-6 grid gap-4 md:grid-cols-4">
          <div className="space-y-2">
            <Label>{t("User")}</Label>
            <Input value={filterUserId} onChange={(event) => setFilterUserId(event.target.value)} className="kos-input" />
          </div>
          <div className="space-y-2">
            <Label>{t("Profile")}</Label>
            <Input value={filterProfile} onChange={(event) => setFilterProfile(event.target.value)} className="kos-input" />
          </div>
          <div className="space-y-2">
            <Label>{t("From Date")}</Label>
            <Input type="date" value={filterDateFrom} onChange={(event) => setFilterDateFrom(event.target.value)} className="kos-input" />
          </div>
          <div className="space-y-2 flex items-end">
            <Button className="w-full kos-gradient-btn text-white" onClick={load}>
              <Filter className="mr-2 h-4 w-4" />
              {t("Apply Filters")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="kos-card">
          <div className="card-gradient-top" />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Total Sessions")}</p>
                <p className="text-2xl font-bold">{sessions.length}</p>
              </div>
              <MessageSquare className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Today")}</p>
                <p className="text-2xl font-bold text-emerald-600">
                  {sessions.filter((session) => formatRiyadhDateKey(session.created_at) === today).length}
                </p>
              </div>
              <MessageSquare className="h-8 w-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">{t("Loading...")}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Title")}</TableHead>
                  <TableHead>{t("User")}</TableHead>
                  <TableHead>{t("Profile")}</TableHead>
                  <TableHead>{t("Created")}</TableHead>
                  <TableHead className="text-right">{t("Actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((session) => (
                  <TableRow key={session.id}>
                    <TableCell className="font-medium max-w-[200px] truncate">{safeText(session.title || t("Untitled"))}</TableCell>
                    <TableCell className="text-xs font-mono max-w-[150px] truncate">{session.user_id}</TableCell>
                    <TableCell>{session.profile_name ? safeText(session.profile_name) : <Badge variant="secondary">{t("default")}</Badge>}</TableCell>
                    <TableCell className="text-xs">{formatRiyadhDateTime(session.created_at)}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => viewSession(session.id)}>
                        <Eye className="h-4 w-4 text-indigo-600" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {sessions.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      {t("No sessions found.")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={selectedSession !== null} onOpenChange={(open) => !open && setSelectedSession(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("Session Detail")}</DialogTitle>
          </DialogHeader>
          {selectedSession && (
            <div className="space-y-3">
              {selectedSession.messages.map((message) => (
                <div
                  key={message.id}
                  className={`p-3 rounded-xl ${
                    message.role === "user"
                      ? "bg-gradient-to-r from-indigo-50 to-blue-50 ml-8 border border-indigo-100"
                      : "bg-gradient-to-r from-gray-50 to-gray-100 mr-8 border border-gray-200"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={message.role === "user" ? "default" : "secondary"}>
                      {message.role}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{formatRiyadhDateTime(message.created_at)}</span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{safeText(message.content)}</p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
