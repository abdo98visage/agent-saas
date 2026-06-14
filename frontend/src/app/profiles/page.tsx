"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { adminApi, type Profile } from "@/lib/api/agentService";
import { toast } from "sonner";
import { Plus, Trash2, Eye, Edit } from "lucide-react";
import apiClient from "@/lib/api/client";
import { getErrorMessage } from "@/lib/api/errors";

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editProfile, setEditProfile] = useState<Profile | null>(null);
  const [viewMd, setViewMd] = useState("");
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    soul_md: "",
    agents_md: "",
    skills: "",
    system_prompt: "",
  });
  const [editFormData, setEditFormData] = useState({
    name: "",
    soul_md: "",
    agents_md: "",
    skills: "",
    system_prompt: "",
    is_active: true,
  });

  const load = async () => {
    const response = await apiClient.get("/admin/profiles");
    setProfiles(response.data.profiles || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const response = await apiClient.get("/admin/profiles");
      if (!cancelled) {
        setProfiles(response.data.profiles || []);
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
      await apiClient.post("/admin/profiles", {
        ...formData,
        slug: formData.slug || formData.name.toLowerCase().replace(/\s+/g, "-"),
        skills: formData.skills.split(",").map((skill) => skill.trim()).filter(Boolean),
      });
      toast.success("Profile created");
      setShowDialog(false);
      setFormData({ name: "", slug: "", soul_md: "", agents_md: "", skills: "", system_prompt: "" });
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to create profile"));
    }
  };

  const handleEdit = (profile: Profile) => {
    setEditProfile(profile);
    setEditFormData({
      name: profile.name,
      soul_md: profile.soul_md || "",
      agents_md: profile.agents_md || "",
      skills: (profile.skills || []).join(", "),
      system_prompt: profile.system_prompt || "",
      is_active: profile.is_active,
    });
    setShowEditDialog(true);
  };

  const handleUpdate = async () => {
    if (!editProfile) return;

    try {
      await adminApi.updateProfile(editProfile.id, {
        name: editFormData.name,
        soul_md: editFormData.soul_md,
        agents_md: editFormData.agents_md,
        skills: editFormData.skills.split(",").map((skill) => skill.trim()).filter(Boolean),
        system_prompt: editFormData.system_prompt,
        is_active: editFormData.is_active,
      });
      toast.success("Profile updated");
      setShowEditDialog(false);
      setEditProfile(null);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to update profile"));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this profile?")) return;

    try {
      await apiClient.delete(`/admin/profiles/${id}`);
      toast.success("Profile deleted");
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to delete profile"));
    }
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">Hermes Profiles</h1>
          <p className="text-muted-foreground mt-1">Manage AGENTS.md, soul, skills, and system prompts per role.</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <Plus className="mr-2 h-4 w-4" />
              Add Profile
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Profile</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={formData.name} onChange={(event) => setFormData({ ...formData, name: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>Slug</Label>
                <Input value={formData.slug} onChange={(event) => setFormData({ ...formData, slug: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>SOUL.md</Label>
                <Input value={formData.soul_md} onChange={(event) => setFormData({ ...formData, soul_md: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>Skills</Label>
                <Input value={formData.skills} onChange={(event) => setFormData({ ...formData, skills: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>AGENTS.md</Label>
                <textarea
                  className="w-full min-h-[200px] p-3 border rounded-xl text-sm font-mono bg-gray-50"
                  value={formData.agents_md}
                  onChange={(event) => setFormData({ ...formData, agents_md: event.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>System Prompt</Label>
                <Input value={formData.system_prompt} onChange={(event) => setFormData({ ...formData, system_prompt: event.target.value })} className="kos-input" />
              </div>
              <Button className="w-full kos-gradient-btn text-white" onClick={handleCreate}>
                Create Profile
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {profiles.map((profile) => (
                <Card key={profile.id} className="kos-card relative">
                  <div className="card-gradient-top" />
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-lg">{profile.name}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-1">{profile.slug}</p>
                    </div>
                    <Badge
                      variant={profile.is_active ? "default" : "secondary"}
                      className={profile.is_active ? "kos-badge-green" : "kos-badge-gray"}
                    >
                      {profile.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm">{profile.soul_md || "—"}</p>
                    <div>
                      <span className="text-xs text-muted-foreground">Skills:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(profile.skills || []).map((skill) => (
                          <Badge key={skill} variant="outline" className="text-xs">
                            {skill}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-2 pt-2">
                      <Button variant="outline" size="sm" onClick={() => setViewMd(profile.agents_md || profile.agents_md_preview)}>
                        <Eye className="h-3 w-3 mr-1" />
                        View
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => handleEdit(profile)}>
                        <Edit className="h-3 w-3 text-blue-500 mr-1" />
                        Edit
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => handleDelete(profile.id)}>
                        <Trash2 className="h-3 w-3 text-red-500" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {profiles.length === 0 && (
                <p className="text-muted-foreground col-span-2 text-center py-4">No profiles created yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={viewMd.length > 0} onOpenChange={(open) => !open && setViewMd("")}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>AGENTS.md</DialogTitle>
          </DialogHeader>
          <pre className="whitespace-pre-wrap text-sm font-mono bg-gray-100 p-4 rounded-xl">
            {viewMd || "No AGENTS.md content."}
          </pre>
        </DialogContent>
      </Dialog>

      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Profile</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={editFormData.name} onChange={(event) => setEditFormData({ ...editFormData, name: event.target.value })} className="kos-input" />
            </div>
            <div className="space-y-2">
              <Label>SOUL.md</Label>
              <Input value={editFormData.soul_md} onChange={(event) => setEditFormData({ ...editFormData, soul_md: event.target.value })} className="kos-input" />
            </div>
            <div className="space-y-2">
              <Label>Skills</Label>
              <Input value={editFormData.skills} onChange={(event) => setEditFormData({ ...editFormData, skills: event.target.value })} className="kos-input" />
            </div>
            <div className="space-y-2">
              <Label>AGENTS.md</Label>
              <textarea
                className="w-full min-h-[200px] p-3 border rounded-xl text-sm font-mono bg-gray-50"
                value={editFormData.agents_md}
                onChange={(event) => setEditFormData({ ...editFormData, agents_md: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>System Prompt</Label>
              <Input value={editFormData.system_prompt} onChange={(event) => setEditFormData({ ...editFormData, system_prompt: event.target.value })} className="kos-input" />
            </div>
            <div className="flex items-center justify-between">
              <Label>Active</Label>
              <Switch
                checked={editFormData.is_active}
                onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
              />
            </div>
            <Button className="w-full kos-gradient-btn text-white" onClick={handleUpdate}>
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
