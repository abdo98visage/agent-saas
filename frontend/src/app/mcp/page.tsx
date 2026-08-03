"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  adminApi,
  type McpServer,
  type Profile,
  type ProfileMcpBinding,
} from "@/lib/api/agentService";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";
import { Edit, Plug, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

type ServerForm = {
  name: string;
  slug: string;
  description: string;
  url: string;
  auth_type: "none" | "bearer" | "api_key";
  credential_mode: "platform" | "user";
  api_key_header: string;
  credential: string;
  is_active: boolean;
};

type BindingDraft = {
  allowed_tools: string[];
  approval_required_tools: string[];
  is_active: boolean;
  exists: boolean;
};

const emptyForm: ServerForm = {
  name: "",
  slug: "",
  description: "",
  url: "",
  auth_type: "none",
  credential_mode: "user",
  api_key_header: "X-API-Key",
  credential: "",
  is_active: true,
};

export default function McpPage() {
  const { t } = useI18n();
  const [servers, setServers] = useState<McpServer[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, BindingDraft>>({});
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<McpServer | null>(null);
  const [form, setForm] = useState<ServerForm>(emptyForm);
  const [saving, setSaving] = useState(false);

  const applyBindings = (serverRows: McpServer[], bindingRows: ProfileMcpBinding[]) => {
    const bindingMap = new Map(bindingRows.map((binding) => [binding.server_id, binding]));
    setDrafts(Object.fromEntries(serverRows.map((server) => {
      const binding = bindingMap.get(server.id);
      return [server.id, {
        allowed_tools: binding?.allowed_tools || [],
        approval_required_tools: binding?.approval_required_tools || [],
        is_active: binding?.is_active ?? true,
        exists: Boolean(binding),
      }];
    })));
  };

  const loadServers = async () => {
    const response = await adminApi.getMcpServers();
    const rows = response.data.servers || [];
    setServers(rows);
    return rows as McpServer[];
  };

  const loadBindings = async (profileId: string, serverRows = servers) => {
    if (!profileId) {
      applyBindings(serverRows, []);
      return;
    }
    const response = await adminApi.getProfileMcpBindings(profileId);
    applyBindings(serverRows, response.data.bindings || []);
  };

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const [serverResponse, profileResponse] = await Promise.all([
          adminApi.getMcpServers(),
          adminApi.getProfiles(),
        ]);
        if (cancelled) return;
        const serverRows = serverResponse.data.servers || [];
        const profileRows = profileResponse.data.profiles || [];
        setServers(serverRows);
        setProfiles(profileRows);
        const firstProfileId = profileRows[0]?.id || "";
        setSelectedProfileId(firstProfileId);
        if (firstProfileId) {
          const bindingResponse = await adminApi.getProfileMcpBindings(firstProfileId);
          if (!cancelled) applyBindings(serverRows, bindingResponse.data.bindings || []);
        } else {
          applyBindings(serverRows, []);
        }
      } catch (error: unknown) {
        toast.error(getErrorMessage(error, "Failed to load MCP configuration"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => { cancelled = true; };
  }, []); // Initial control-plane snapshot only.

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (server: McpServer) => {
    setEditing(server);
    setForm({
      name: server.name,
      slug: server.slug,
      description: server.description || "",
      url: server.url,
      auth_type: server.auth_type,
      credential_mode: server.credential_mode,
      api_key_header: server.api_key_header,
      credential: "",
      is_active: server.is_active,
    });
    setDialogOpen(true);
  };

  const saveServer = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...form };
      if (!form.credential) delete payload.credential;
      if (editing) {
        delete payload.slug;
        await adminApi.updateMcpServer(editing.id, payload);
        toast.success(t("MCP server updated"));
      } else {
        await adminApi.createMcpServer(payload);
        toast.success(t("MCP server created"));
      }
      setDialogOpen(false);
      const rows = await loadServers();
      await loadBindings(selectedProfileId, rows);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to save MCP server")));
    } finally {
      setSaving(false);
    }
  };

  const discover = async (server: McpServer) => {
    const credential = server.credential_mode === "user" && server.auth_type !== "none"
      ? window.prompt(t("Enter a temporary credential for discovery")) || undefined
      : undefined;
    try {
      const response = await adminApi.discoverMcpServer(server.id, credential);
      if (response.data.status === "error") throw new Error(response.data.detail);
      toast.success(t("MCP tools discovered"));
      const rows = await loadServers();
      await loadBindings(selectedProfileId, rows);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("MCP discovery failed")));
    }
  };

  const removeServer = async (server: McpServer) => {
    if (!window.confirm(t("Delete this MCP server and all profile bindings?"))) return;
    try {
      await adminApi.deleteMcpServer(server.id);
      const rows = await loadServers();
      await loadBindings(selectedProfileId, rows);
      toast.success(t("MCP server deleted"));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to delete MCP server")));
    }
  };

  const toggleTool = (serverId: string, tool: string, field: "allowed_tools" | "approval_required_tools") => {
    setDrafts((current) => {
      const draft = current[serverId];
      const selected = draft[field].includes(tool);
      const next = selected ? draft[field].filter((item) => item !== tool) : [...draft[field], tool];
      const updated = { ...draft, [field]: next };
      if (field === "allowed_tools" && selected) {
        updated.approval_required_tools = updated.approval_required_tools.filter((item) => item !== tool);
      }
      return { ...current, [serverId]: updated };
    });
  };

  const saveBinding = async (server: McpServer) => {
    if (!selectedProfileId) return;
    const draft = drafts[server.id];
    if (draft.is_active && draft.allowed_tools.length === 0) {
      toast.error(t("Select at least one allowed tool"));
      return;
    }
    try {
      await adminApi.saveProfileMcpBinding(selectedProfileId, {
        server_id: server.id,
        allowed_tools: draft.allowed_tools,
        approval_required_tools: draft.approval_required_tools,
        is_active: draft.is_active,
      });
      await loadBindings(selectedProfileId);
      toast.success(t("Profile MCP access saved"));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to save profile MCP access")));
    }
  };

  const removeBinding = async (server: McpServer) => {
    if (!selectedProfileId) return;
    try {
      await adminApi.deleteProfileMcpBinding(selectedProfileId, server.id);
      await loadBindings(selectedProfileId);
      toast.success(t("Profile MCP access removed"));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to remove profile MCP access")));
    }
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">MCP</h1>
          <p className="text-muted-foreground mt-1">{t("Manage approved MCP servers, tools, and profile access.")}</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />{t("Add MCP Server")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader><DialogTitle>{editing ? t("Edit MCP Server") : t("Add MCP Server")}</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2"><Label>{t("Name")}</Label><Input className="kos-input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
                <div className="space-y-2"><Label>{t("Slug")}</Label><Input className="kos-input" disabled={Boolean(editing)} value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "-") })} /></div>
              </div>
              <div className="space-y-2"><Label>{t("Description")}</Label><Input className="kos-input" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
              <div className="space-y-2"><Label>{t("HTTPS MCP URL")}</Label><Input className="kos-input" placeholder="https://mcp.example.com/mcp" value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} /></div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>{t("Authentication")}</Label>
                  <select className="w-full h-10 rounded-xl border bg-white px-3 text-sm" value={form.auth_type} onChange={(event) => setForm({ ...form, auth_type: event.target.value as ServerForm["auth_type"] })}>
                    <option value="none">{t("No authentication")}</option><option value="bearer">Bearer token</option><option value="api_key">API key</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>{t("Credential ownership")}</Label>
                  <select className="w-full h-10 rounded-xl border bg-white px-3 text-sm" value={form.credential_mode} onChange={(event) => setForm({ ...form, credential_mode: event.target.value as ServerForm["credential_mode"] })}>
                    <option value="platform">{t("Managed by administrator")}</option><option value="user">{t("Provided by each employee")}</option>
                  </select>
                </div>
              </div>
              {form.auth_type === "api_key" && <div className="space-y-2"><Label>{t("API key header")}</Label><Input className="kos-input" value={form.api_key_header} onChange={(event) => setForm({ ...form, api_key_header: event.target.value })} /></div>}
              {form.auth_type !== "none" && <div className="space-y-2"><Label>{form.credential_mode === "platform" ? t("Platform credential") : t("Temporary discovery credential")}</Label><Input type="password" className="kos-input" value={form.credential} onChange={(event) => setForm({ ...form, credential: event.target.value })} placeholder={editing ? t("Leave blank to keep the current credential") : ""} /></div>}
              <div className="flex items-center justify-between"><Label>{t("Active")}</Label><Switch checked={form.is_active} onCheckedChange={(checked) => setForm({ ...form, is_active: checked })} /></div>
              <Button className="w-full kos-gradient-btn text-white" disabled={saving || !form.name || !form.slug || !form.url} onClick={saveServer}>{saving ? t("Saving...") : t("Save")}</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="kos-card"><CardContent className="pt-6 flex items-center justify-between"><div><p className="text-sm text-muted-foreground">{t("MCP Servers")}</p><p className="text-2xl font-bold">{servers.length}</p></div><Plug className="h-8 w-8 text-indigo-600" /></CardContent></Card>
        <Card className="kos-card"><CardContent className="pt-6"><p className="text-sm text-muted-foreground">{t("Connected")}</p><p className="text-2xl font-bold text-emerald-600">{servers.filter((server) => !server.last_error && server.last_checked_at).length}</p></CardContent></Card>
        <Card className="kos-card"><CardContent className="pt-6"><p className="text-sm text-muted-foreground">{t("Discovered Tools")}</p><p className="text-2xl font-bold">{servers.reduce((sum, server) => sum + server.discovered_tools.length, 0)}</p></CardContent></Card>
      </div>

      <Card className="kos-card">
        <CardHeader><CardTitle>{t("Approved MCP Servers")}</CardTitle></CardHeader>
        <CardContent>
          {loading ? <p className="text-muted-foreground">{t("Loading...")}</p> : <div className="grid gap-4 md:grid-cols-2">
            {servers.map((server) => <Card key={server.id} className="kos-card">
              <CardHeader className="flex flex-row items-start justify-between">
                <div><CardTitle className="text-lg">{server.name}</CardTitle><p className="text-xs text-muted-foreground mt-1">{server.url}</p></div>
                <Badge className={server.is_active ? "kos-badge-green" : "kos-badge-gray"}>{server.is_active ? t("Active") : t("Inactive")}</Badge>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm">{server.description || t("No description")}</p>
                <div className="flex flex-wrap gap-1">{server.discovered_tools.map((tool) => <Badge key={tool.name} variant="outline">{tool.name}</Badge>)}</div>
                {server.last_error && <p className="text-sm text-red-600">{server.last_error}</p>}
                <p className="text-xs text-muted-foreground">{t("Profile bindings")}: {server.binding_count}</p>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" size="sm" onClick={() => void discover(server)}><RefreshCw className="h-3 w-3 mr-1" />{t("Discover")}</Button>
                  <Button variant="outline" size="sm" onClick={() => openEdit(server)}><Edit className="h-3 w-3 mr-1" />{t("Edit")}</Button>
                  <Button variant="outline" size="sm" onClick={() => void removeServer(server)}><Trash2 className="h-3 w-3 text-red-500" /></Button>
                </div>
              </CardContent>
            </Card>)}
            {servers.length === 0 && <p className="text-muted-foreground col-span-2 text-center py-8">{t("No MCP servers configured.")}</p>}
          </div>}
        </CardContent>
      </Card>

      <Card className="kos-card">
        <CardHeader><CardTitle>{t("Profile MCP Access")}</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          <div className="max-w-md space-y-2"><Label>{t("Profile")}</Label><select className="w-full h-10 rounded-xl border bg-white px-3 text-sm" value={selectedProfileId} onChange={(event) => { const id = event.target.value; setSelectedProfileId(id); void loadBindings(id); }}><option value="">{t("Select profile")}</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></div>
          {selectedProfileId && <div className="grid gap-4 md:grid-cols-2">{servers.map((server) => {
            const draft = drafts[server.id] || { allowed_tools: [], approval_required_tools: [], is_active: true, exists: false };
            return <Card key={server.id} className="kos-card"><CardHeader className="flex flex-row items-center justify-between"><CardTitle className="text-base">{server.name}</CardTitle><Switch disabled={!server.is_active} checked={draft.is_active} onCheckedChange={(checked) => setDrafts((current) => ({ ...current, [server.id]: { ...draft, is_active: checked } }))} /></CardHeader><CardContent className="space-y-3">
              {server.discovered_tools.map((tool) => <div key={tool.name} className="rounded-xl border p-3"><div className="font-medium text-sm">{tool.name}</div><div className="mt-2 flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><input type="checkbox" checked={draft.allowed_tools.includes(tool.name)} onChange={() => toggleTool(server.id, tool.name, "allowed_tools")} />{t("Allow")}</label><label className="flex items-center gap-2"><input type="checkbox" disabled={!draft.allowed_tools.includes(tool.name)} checked={draft.approval_required_tools.includes(tool.name)} onChange={() => toggleTool(server.id, tool.name, "approval_required_tools")} />{t("Require approval")}</label></div></div>)}
              {server.discovered_tools.length === 0 && <p className="text-sm text-muted-foreground">{t("Discover tools before assigning this server.")}</p>}
              <div className="flex justify-end gap-2"><Button size="sm" className="kos-gradient-btn text-white" disabled={!server.is_active || server.discovered_tools.length === 0} onClick={() => void saveBinding(server)}><Save className="h-3 w-3 mr-1" />{t("Save")}</Button>{draft.exists && <Button size="sm" variant="outline" onClick={() => void removeBinding(server)}><Trash2 className="h-3 w-3 text-red-500 mr-1" />{t("Remove")}</Button>}</div>
            </CardContent></Card>;
          })}</div>}
        </CardContent>
      </Card>
    </div>
  );
}
