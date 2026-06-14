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

export default function AssignmentsPage() {
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
      toast.success("Assignment created");
      setShowDialog(false);
      setFormData({ user_id: "", profile_id: "", priority: "0" });
      await loadAll();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to create assignment"));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this assignment?")) return;

    try {
      await apiClient.delete(`/admin/assignments/${id}`);
      toast.success("Assignment removed");
      await loadAll();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to remove assignment"));
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
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">Profile Assignments</h1>
          <p className="text-muted-foreground mt-1">Mount employees to Hermes profiles and control priority order.</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <Plus className="mr-2 h-4 w-4" />
              Create Assignment
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Assign Profile</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Employee</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.user_id}
                  onChange={(event) => setFormData({ ...formData, user_id: event.target.value })}
                >
                  <option value="">Select employee...</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.full_name || user.email}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Profile</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.profile_id}
                  onChange={(event) => setFormData({ ...formData, profile_id: event.target.value })}
                >
                  <option value="">Select profile...</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Priority</Label>
                <Input
                  type="number"
                  value={formData.priority}
                  onChange={(event) => setFormData({ ...formData, priority: event.target.value })}
                  className="kos-input"
                />
              </div>
              <Button className="w-full kos-gradient-btn text-white" onClick={handleCreate}>
                Save Assignment
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
                <p className="text-sm text-muted-foreground">Assignments</p>
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
                <p className="text-sm text-muted-foreground">Employees</p>
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
                <p className="text-sm text-muted-foreground">Profiles</p>
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
            <p className="text-muted-foreground">Loading...</p>
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
                        <p className="text-sm font-medium">{getUserName(assignment.user_id)}</p>
                        <p className="text-xs text-muted-foreground">Employee</p>
                      </div>
                    </div>
                    <span className="text-muted-foreground text-xl">→</span>
                    <div className="flex items-center gap-2">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-100 to-purple-200 flex items-center justify-center">
                        <Bot className="h-5 w-5 text-purple-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">{getProfileName(assignment.profile_id)}</p>
                        <Badge variant="secondary" className="text-xs kos-badge-purple">
                          Priority: {assignment.priority}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(assignment.id)}>
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              ))}
              {assignments.length === 0 && (
                <p className="text-muted-foreground text-center py-8">No assignments yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
