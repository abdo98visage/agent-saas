"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, User, Bot, Link2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api/client";
import { type Employee, type ProfileAssignment, type Profile } from "@/lib/api/agentService";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";

export default function AssignmentsPage() {
  const { t, safeText } = useI18n();
  const [assignments, setAssignments] = useState<ProfileAssignment[]>([]);
  const [users, setUsers] = useState<Employee[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [formData, setFormData] = useState({ user_id: "", profile_id: "", priority: "0" });

  const loadAll = async () => {
    setLoading(true);
    const [assignmentsRes, usersRes, profilesRes] = await Promise.all([
      apiClient.get("/admin/assignments"),
      apiClient.get("/admin/employees"),
      apiClient.get("/admin/profiles"),
    ]);
    setAssignments(assignmentsRes.data.assignments || []);
    setUsers(usersRes.data.employees || []);
    setProfiles(profilesRes.data.profiles || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const [assignmentsRes, usersRes, profilesRes] = await Promise.all([
        apiClient.get("/admin/assignments"),
        apiClient.get("/admin/employees"),
        apiClient.get("/admin/profiles"),
      ]);
      if (!cancelled) {
        setAssignments(assignmentsRes.data.assignments || []);
        setUsers(usersRes.data.employees || []);
        setProfiles(profilesRes.data.profiles || []);
        setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleCreate = async () => {
    try {
      await apiClient.post("/admin/assignments", {
        ...formData,
        priority: Number.parseInt(formData.priority, 10) || 0,
      });
      toast.success(t("Assignment created"));
      setShowDialog(false);
      setFormData({ user_id: "", profile_id: "", priority: "0" });
      await loadAll();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to create assignment")));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t("Delete this assignment?"))) return;

    try {
      await apiClient.delete(`/admin/assignments/${id}`);
      toast.success(t("Assignment removed"));
      await loadAll();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to remove assignment")));
    }
  };

  const getUserName = (userId: string) => {
    const user = users.find((item) => item.id === userId);
    return user ? user.full_name || user.email : userId;
  };

  const getProfileName = (profileId: string) => {
    const profile = profiles.find((item) => item.id === profileId);
    return profile ? profile.name : profileId;
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Profile Assignments")}</h1>
          <p className="text-muted-foreground mt-1">{t("Assign employees to smart agent profiles and control priority order.")}</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <Plus className="mr-2 h-4 w-4" />
              {t("Create Assignment")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("Assign Profile")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>{t("Employee")}</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.user_id}
                  onChange={(event) => setFormData({ ...formData, user_id: event.target.value })}
                >
                  <option value="">{t("Select employee...")}</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.full_name || user.email}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>{t("Profile")}</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.profile_id}
                  onChange={(event) => setFormData({ ...formData, profile_id: event.target.value })}
                >
                  <option value="">{t("Select profile...")}</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {safeText(profile.name)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>{t("Priority")}</Label>
                <Input
                  type="number"
                  value={formData.priority}
                  onChange={(event) => setFormData({ ...formData, priority: event.target.value })}
                  className="kos-input"
                />
                <p className="text-xs text-muted-foreground">0 = أعلى أولوية / Highest priority</p>
              </div>
              <Button className="w-full kos-gradient-btn text-white" onClick={handleCreate}>
                {t("Save Assignment")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="kos-card">
          <div className="card-gradient-top" />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Assignments")}</p>
                <p className="text-2xl font-bold">{assignments.length}</p>
              </div>
              <Link2 className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Employees")}</p>
                <p className="text-2xl font-bold text-emerald-600">{users.length}</p>
              </div>
              <User className="h-8 w-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #8B5CF6, #7C3AED)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Profiles")}</p>
                <p className="text-2xl font-bold text-purple-600">{profiles.length}</p>
              </div>
              <Bot className="h-8 w-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">{t("Loading...")}</p>
          ) : (
            <div className="space-y-3">
              {assignments.map((assignment, index) => (
                <div
                  key={assignment.id}
                  className="flex items-center justify-between p-4 rounded-xl border hover:border-indigo-200 hover:bg-indigo-50/30 transition-all kos-animate-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-200 flex items-center justify-center">
                        <User className="h-5 w-5 text-emerald-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium" dir="auto">{getUserName(assignment.user_id)}</p>
                        <p className="text-xs text-muted-foreground">{t("Employee")}</p>
                      </div>
                    </div>
                    <span className="text-muted-foreground text-xl">→</span>
                    <div className="flex items-center gap-2">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-100 to-purple-200 flex items-center justify-center">
                        <Bot className="h-5 w-5 text-purple-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium" dir="auto">{safeText(getProfileName(assignment.profile_id))}</p>
                        <div className="flex flex-wrap items-center gap-1 mt-1">
                          <Badge variant="secondary" className="text-xs kos-badge-purple">
                            {t("Priority")}: {assignment.priority}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            {t(assignment.profile_runtime_type === "direct_llm" ? "Direct Model" : "Smart Agents")}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={assignment.profile_sync_status === "synced" ? "text-[10px] text-emerald-700" : "text-[10px] text-amber-700"}
                          >
                            {t(assignment.profile_sync_status || "pending")}
                          </Badge>
                          {assignment.profile_provider_key_id ? (
                            <Badge variant="outline" className="text-[10px] text-emerald-700">{t("key ready")}</Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px] text-amber-700">{t("no profile key")}</Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(assignment.id)}>
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              ))}
              {assignments.length === 0 && (
                <p className="text-muted-foreground text-center py-8">{t("No assignments yet.")}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
