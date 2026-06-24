"use client";

import { type ChangeEvent, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { adminApi, type Profile, type SkillDefinition } from "@/lib/api/agentService";
import { toast } from "sonner";
import { Plus, Trash2, Eye, Edit, RefreshCw } from "lucide-react";
import apiClient from "@/lib/api/client";
import { getErrorMessage } from "@/lib/api/errors";

const parseCsv = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);
const getSelectedValues = (event: ChangeEvent<HTMLSelectElement>) =>
  Array.from(event.target.selectedOptions, (option) => option.value);
const buildSkillOptions = (catalogSkills: SkillDefinition[], selectedSkills: string[]) => {
  const knownSlugs = new Set(catalogSkills.map((skill) => skill.slug));
  const legacySkills = selectedSkills
    .filter((skillSlug) => !knownSlugs.has(skillSlug))
    .map((skillSlug) => ({
      id: `legacy-${skillSlug}`,
      slug: skillSlug,
      name: `${skillSlug} (legacy)`,
    }));

  return [
    ...catalogSkills.map((skill) => ({ id: skill.id, slug: skill.slug, name: skill.name })),
    ...legacySkills,
  ];
};

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
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
    skills: [] as string[],
    system_prompt: "",
    max_tokens_per_day: "",
    max_requests_per_day: "",
    daily_cost_budget: "",
    allowed_providers: "minimax",
    allowed_mcp_servers: "",
    allowed_tools: "",
    approval_required_tools: "",
  });
  const [editFormData, setEditFormData] = useState({
    name: "",
    soul_md: "",
    agents_md: "",
    skills: [] as string[],
    system_prompt: "",
    is_active: true,
    max_tokens_per_day: "",
    max_requests_per_day: "",
    daily_cost_budget: "",
    allowed_providers: "",
    allowed_mcp_servers: "",
    allowed_tools: "",
    approval_required_tools: "",
  });
  const createSkillOptions = buildSkillOptions(skills, formData.skills);
  const editSkillOptions = buildSkillOptions(skills, editFormData.skills);

  const load = async () => {
    const [profilesResponse, skillsResponse] = await Promise.all([
      apiClient.get("/admin/profiles"),
      adminApi.getSkills(),
    ]);
    setProfiles(profilesResponse.data.profiles || []);
    setSkills(skillsResponse.data.skills || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const [profilesResponse, skillsResponse] = await Promise.all([
        apiClient.get("/admin/profiles"),
        adminApi.getSkills(),
      ]);
      if (!cancelled) {
        setProfiles(profilesResponse.data.profiles || []);
        setSkills(skillsResponse.data.skills || []);
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
        skills: formData.skills,
        max_tokens_per_day: formData.max_tokens_per_day ? Number.parseInt(formData.max_tokens_per_day, 10) : null,
        max_requests_per_day: formData.max_requests_per_day ? Number.parseInt(formData.max_requests_per_day, 10) : null,
        daily_cost_budget: formData.daily_cost_budget ? Number.parseInt(formData.daily_cost_budget, 10) : null,
        allowed_providers: parseCsv(formData.allowed_providers),
        allowed_mcp_servers: parseCsv(formData.allowed_mcp_servers),
        allowed_tools: parseCsv(formData.allowed_tools),
        approval_required_tools: parseCsv(formData.approval_required_tools),
      });
      toast.success("Profile created");
      setShowDialog(false);
      setFormData({
        name: "", slug: "", soul_md: "", agents_md: "", skills: [], system_prompt: "",
        max_tokens_per_day: "", max_requests_per_day: "", daily_cost_budget: "",
        allowed_providers: "minimax", allowed_mcp_servers: "", allowed_tools: "", approval_required_tools: "",
      });
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
      skills: profile.skills || [],
      system_prompt: profile.system_prompt || "",
      is_active: profile.is_active,
      max_tokens_per_day: profile.max_tokens_per_day?.toString() || "",
      max_requests_per_day: profile.max_requests_per_day?.toString() || "",
      daily_cost_budget: profile.daily_cost_budget?.toString() || "",
      allowed_providers: (profile.allowed_providers || []).join(", "),
      allowed_mcp_servers: (profile.allowed_mcp_servers || []).join(", "),
      allowed_tools: (profile.allowed_tools || []).join(", "),
      approval_required_tools: (profile.approval_required_tools || []).join(", "),
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
        skills: editFormData.skills,
        system_prompt: editFormData.system_prompt,
        is_active: editFormData.is_active,
        max_tokens_per_day: editFormData.max_tokens_per_day ? Number.parseInt(editFormData.max_tokens_per_day, 10) : null,
        max_requests_per_day: editFormData.max_requests_per_day ? Number.parseInt(editFormData.max_requests_per_day, 10) : null,
        daily_cost_budget: editFormData.daily_cost_budget ? Number.parseInt(editFormData.daily_cost_budget, 10) : null,
        allowed_providers: parseCsv(editFormData.allowed_providers),
        allowed_mcp_servers: parseCsv(editFormData.allowed_mcp_servers),
        allowed_tools: parseCsv(editFormData.allowed_tools),
        approval_required_tools: parseCsv(editFormData.approval_required_tools),
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

  const handleSync = async (id: string) => {
    try {
      await apiClient.post(`/admin/profiles/${id}/sync`);
      toast.success("Profile sync requested");
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to sync profile"));
    }
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">بروفايلات Hermes</h1>
          <p className="text-muted-foreground mt-1">إدارة AGENTS.md وملف soul والمهارات وتعليمات النظام لكل دور.</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <Plus className="mr-2 h-4 w-4" />
              إضافة بروفايل
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
                <select
                  multiple
                  value={formData.skills}
                  onChange={(event) => setFormData({ ...formData, skills: getSelectedValues(event) })}
                  className="w-full min-h-[160px] rounded-xl border bg-background px-3 py-2 text-sm"
                >
                  {createSkillOptions.map((skill) => (
                    <option key={skill.id} value={skill.slug}>
                      {skill.name} ({skill.slug})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">Hold Ctrl or Cmd to select multiple skills.</p>
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
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <Label>Daily Tokens</Label>
                  <Input type="number" value={formData.max_tokens_per_day} onChange={(event) => setFormData({ ...formData, max_tokens_per_day: event.target.value })} className="kos-input" />
                </div>
                <div className="space-y-2">
                  <Label>Daily Requests</Label>
                  <Input type="number" value={formData.max_requests_per_day} onChange={(event) => setFormData({ ...formData, max_requests_per_day: event.target.value })} className="kos-input" />
                </div>
                <div className="space-y-2">
                  <Label>Cost Budget</Label>
                  <Input type="number" value={formData.daily_cost_budget} onChange={(event) => setFormData({ ...formData, daily_cost_budget: event.target.value })} className="kos-input" />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Allowed Providers</Label>
                  <Input value={formData.allowed_providers} onChange={(event) => setFormData({ ...formData, allowed_providers: event.target.value })} className="kos-input" />
                </div>
                <div className="space-y-2">
                  <Label>MCP Servers</Label>
                  <Input value={formData.allowed_mcp_servers} onChange={(event) => setFormData({ ...formData, allowed_mcp_servers: event.target.value })} className="kos-input" />
                </div>
                <div className="space-y-2">
                  <Label>Allowed Tools</Label>
                  <Input value={formData.allowed_tools} onChange={(event) => setFormData({ ...formData, allowed_tools: event.target.value })} className="kos-input" />
                </div>
                <div className="space-y-2">
                  <Label>Approval Tools</Label>
                  <Input value={formData.approval_required_tools} onChange={(event) => setFormData({ ...formData, approval_required_tools: event.target.value })} className="kos-input" />
                </div>
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
                    <div className="flex flex-wrap gap-2 text-xs">
                      <Badge variant="outline">{profile.runtime_type || "hermes"}</Badge>
                      <Badge
                        variant="outline"
                        className={profile.hermes_sync_status === "synced" ? "text-emerald-700 border-emerald-200" : "text-amber-700 border-amber-200"}
                      >
                        {profile.hermes_sync_status || "pending"}
                      </Badge>
                      {profile.version && <Badge variant="outline">v{profile.version}</Badge>}
                    </div>
                    {profile.hermes_sync_error && (
                      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-md p-2">
                        {profile.hermes_sync_error}
                      </p>
                    )}
                    <div>
                      <span className="text-xs text-muted-foreground">Skills:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(profile.skill_details || []).map((skill) => (
                          <Badge key={skill.slug} variant="outline" className="text-xs">
                            {skill.name}
                          </Badge>
                        ))}
                        {(profile.skills || [])
                          .filter((skillSlug) => !(profile.skill_details || []).some((skill) => skill.slug === skillSlug))
                          .map((skillSlug) => (
                          <Badge key={skillSlug} variant="outline" className="text-xs">
                            {skillSlug}
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
                      <Button variant="outline" size="sm" onClick={() => handleSync(profile.id)}>
                        <RefreshCw className="h-3 w-3 mr-1" />
                        Sync
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
              <select
                multiple
                value={editFormData.skills}
                onChange={(event) => setEditFormData({ ...editFormData, skills: getSelectedValues(event) })}
                className="w-full min-h-[160px] rounded-xl border bg-background px-3 py-2 text-sm"
              >
                {editSkillOptions.map((skill) => (
                  <option key={skill.id} value={skill.slug}>
                    {skill.name} ({skill.slug})
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">Hold Ctrl or Cmd to select multiple skills.</p>
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
            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Daily Tokens</Label>
                <Input type="number" value={editFormData.max_tokens_per_day} onChange={(event) => setEditFormData({ ...editFormData, max_tokens_per_day: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>Daily Requests</Label>
                <Input type="number" value={editFormData.max_requests_per_day} onChange={(event) => setEditFormData({ ...editFormData, max_requests_per_day: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>Cost Budget</Label>
                <Input type="number" value={editFormData.daily_cost_budget} onChange={(event) => setEditFormData({ ...editFormData, daily_cost_budget: event.target.value })} className="kos-input" />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Allowed Providers</Label>
                <Input value={editFormData.allowed_providers} onChange={(event) => setEditFormData({ ...editFormData, allowed_providers: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>MCP Servers</Label>
                <Input value={editFormData.allowed_mcp_servers} onChange={(event) => setEditFormData({ ...editFormData, allowed_mcp_servers: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>Allowed Tools</Label>
                <Input value={editFormData.allowed_tools} onChange={(event) => setEditFormData({ ...editFormData, allowed_tools: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>Approval Tools</Label>
                <Input value={editFormData.approval_required_tools} onChange={(event) => setEditFormData({ ...editFormData, approval_required_tools: event.target.value })} className="kos-input" />
              </div>
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
