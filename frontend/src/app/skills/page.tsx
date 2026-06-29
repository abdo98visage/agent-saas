"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { adminApi, type SkillDefinition } from "@/lib/api/agentService";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";
import { toast } from "sonner";
import { Plus, Edit, Trash2, Wrench } from "lucide-react";

export default function SkillsPage() {
  const { t } = useI18n();
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editSkill, setEditSkill] = useState<SkillDefinition | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    description: "",
    instructions_md: "",
    is_active: true,
  });
  const [editFormData, setEditFormData] = useState({
    name: "",
    slug: "",
    description: "",
    instructions_md: "",
    is_active: true,
  });

  const load = async () => {
    const response = await adminApi.getSkills({ include_inactive: true });
    setSkills(response.data.skills || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const response = await adminApi.getSkills({ include_inactive: true });
      if (!cancelled) {
        setSkills(response.data.skills || []);
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
      await adminApi.createSkill({
        ...formData,
        slug: formData.slug || formData.name.toLowerCase().replace(/\s+/g, "-"),
      });
      toast.success(t("Skill created"));
      setShowDialog(false);
      setFormData({ name: "", slug: "", description: "", instructions_md: "", is_active: true });
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to create skill")));
    }
  };

  const handleEdit = (skill: SkillDefinition) => {
    setEditSkill(skill);
    setEditFormData({
      name: skill.name,
      slug: skill.slug,
      description: skill.description || "",
      instructions_md: skill.instructions_md || "",
      is_active: skill.is_active,
    });
    setShowEditDialog(true);
  };

  const handleUpdate = async () => {
    if (!editSkill) return;

    try {
      await adminApi.updateSkill(editSkill.id, editFormData);
      toast.success(t("Skill updated"));
      setShowEditDialog(false);
      setEditSkill(null);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to update skill")));
    }
  };

  const handleDelete = async (skillId: string) => {
    if (!confirm(t("Delete this skill?"))) return;

    try {
      await adminApi.deleteSkill(skillId);
      toast.success(t("Skill deleted"));
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to delete skill")));
    }
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Skills")}</h1>
          <p className="text-muted-foreground mt-1">{t("Create reusable agent skills and attach them to profiles.")}</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <Plus className="mr-2 h-4 w-4" />
              {t("Add Skill")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{t("Create Skill")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>{t("Name")}</Label>
                  <Input value={formData.name} onChange={(event) => setFormData({ ...formData, name: event.target.value })} className="kos-input" />
                </div>
                <div className="space-y-2">
                  <Label>{t("Slug")}</Label>
                  <Input value={formData.slug} onChange={(event) => setFormData({ ...formData, slug: event.target.value })} className="kos-input" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>{t("Description")}</Label>
                <Input value={formData.description} onChange={(event) => setFormData({ ...formData, description: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>{t("Instructions (SKILL.md body)")}</Label>
                <textarea
                  className="w-full min-h-[320px] p-3 border rounded-xl text-sm font-mono bg-gray-50"
                  value={formData.instructions_md}
                  onChange={(event) => setFormData({ ...formData, instructions_md: event.target.value })}
                />
              </div>
              <Button className="w-full kos-gradient-btn text-white" onClick={handleCreate}>
                {t("Create Skill")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="kos-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Total Skills")}</p>
                <p className="text-2xl font-bold">{skills.length}</p>
              </div>
              <Wrench className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{t("Active")}</p>
            <p className="text-2xl font-bold text-emerald-600">{skills.filter((skill) => skill.is_active).length}</p>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{t("Inactive")}</p>
            <p className="text-2xl font-bold text-amber-600">{skills.filter((skill) => !skill.is_active).length}</p>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">{t("Loading...")}</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {skills.map((skill) => (
                <Card key={skill.id} className="kos-card">
                  <div className="card-gradient-top" />
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-lg">{skill.name}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-1">{skill.slug}</p>
                    </div>
                    <Badge className={skill.is_active ? "kos-badge-green" : "kos-badge-gray"}>
                      {skill.is_active ? t("Active") : t("Inactive")}
                    </Badge>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm">{skill.description || t("No description")}</p>
                    <pre className="whitespace-pre-wrap rounded-xl bg-gray-50 border p-3 text-xs max-h-56 overflow-auto">
                      {skill.instructions_md || t("No instructions yet.")}
                    </pre>
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => handleEdit(skill)}>
                        <Edit className="h-3 w-3 mr-1" />
                        {t("Edit")}
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => handleDelete(skill.id)}>
                        <Trash2 className="h-3 w-3 text-red-500 mr-1" />
                        {t("Delete")}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {skills.length === 0 && (
                <p className="text-muted-foreground col-span-2 text-center py-8">{t("No skills defined yet.")}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("Edit Skill")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("Name")}</Label>
                <Input value={editFormData.name} onChange={(event) => setEditFormData({ ...editFormData, name: event.target.value })} className="kos-input" />
              </div>
              <div className="space-y-2">
                <Label>{t("Slug")}</Label>
                <Input value={editFormData.slug} onChange={(event) => setEditFormData({ ...editFormData, slug: event.target.value })} className="kos-input" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t("Description")}</Label>
              <Input value={editFormData.description} onChange={(event) => setEditFormData({ ...editFormData, description: event.target.value })} className="kos-input" />
            </div>
            <div className="space-y-2">
              <Label>{t("Instructions (SKILL.md body)")}</Label>
              <textarea
                className="w-full min-h-[320px] p-3 border rounded-xl text-sm font-mono bg-gray-50"
                value={editFormData.instructions_md}
                onChange={(event) => setEditFormData({ ...editFormData, instructions_md: event.target.value })}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label>{t("Active")}</Label>
              <Switch checked={editFormData.is_active} onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })} />
            </div>
            <Button className="w-full kos-gradient-btn text-white" onClick={handleUpdate}>
              {t("Save Changes")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
