"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, Edit, Key, CreditCard, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api/client";
import { getErrorMessage } from "@/lib/api/errors";

interface ApiKey {
  id: string;
  user_id: string;
  provider: string;
  key_prefix: string;
  is_active: boolean;
  daily_budget: number;
  spent_today: number;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editKey, setEditKey] = useState<ApiKey | null>(null);
  const [formData, setFormData] = useState({
    user_id: "",
    provider: "minimax",
    api_key: "",
    daily_budget: 50000,
  });
  const [editFormData, setEditFormData] = useState({
    is_active: true,
    daily_budget: 50000,
  });

  const load = async () => {
    const response = await apiClient.get("/admin/api-keys");
    setKeys(response.data.api_keys || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const response = await apiClient.get("/admin/api-keys");
      if (!cancelled) {
        setKeys(response.data.api_keys || []);
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
      await apiClient.post("/admin/api-keys", formData);
      toast.success("API key created");
      setShowDialog(false);
      setFormData({ user_id: "", provider: "minimax", api_key: "", daily_budget: 50000 });
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to create API key"));
    }
  };

  const handleEdit = (key: ApiKey) => {
    setEditKey(key);
    setEditFormData({
      is_active: key.is_active,
      daily_budget: key.daily_budget,
    });
    setShowEditDialog(true);
  };

  const handleUpdate = async () => {
    if (!editKey) return;

    try {
      await apiClient.put(`/admin/api-keys/${editKey.id}`, editFormData);
      toast.success("API key updated");
      setShowEditDialog(false);
      setEditKey(null);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to update API key"));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this API key?")) return;

    try {
      await apiClient.delete(`/admin/api-keys/${id}`);
      toast.success("API key deleted");
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to delete API key"));
    }
  };

  const totalBudget = keys.reduce((sum, key) => sum + key.daily_budget, 0);
  const totalSpent = keys.reduce((sum, key) => sum + key.spent_today, 0);

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">API Keys</h1>
          <p className="text-muted-foreground mt-1">Manage employee provider credentials and budgets.</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <Plus className="mr-2 h-4 w-4" />
              Add Key
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create API Key</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>User ID</Label>
                <Input
                  value={formData.user_id}
                  onChange={(event) => setFormData({ ...formData, user_id: event.target.value })}
                  placeholder="Employee UUID"
                  className="kos-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Provider</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.provider}
                  onChange={(event) => setFormData({ ...formData, provider: event.target.value })}
                >
                  <option value="minimax">MiniMax</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>API Key</Label>
                <Input
                  type="password"
                  value={formData.api_key}
                  onChange={(event) => setFormData({ ...formData, api_key: event.target.value })}
                  placeholder="sk-..."
                  className="kos-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Daily Budget</Label>
                <Input
                  type="number"
                  value={formData.daily_budget}
                  onChange={(event) => setFormData({ ...formData, daily_budget: Number.parseInt(event.target.value, 10) || 0 })}
                  className="kos-input"
                />
              </div>
              <Button className="w-full kos-gradient-btn text-white" onClick={handleCreate}>
                Create Key
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
                <p className="text-sm text-muted-foreground">Keys</p>
                <p className="text-2xl font-bold">{keys.length}</p>
              </div>
              <Key className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #F59E0B, #D97706)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Budget</p>
                <p className="text-2xl font-bold text-amber-600">{totalBudget.toLocaleString()}</p>
              </div>
              <CreditCard className="h-8 w-8 text-amber-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Spent Today</p>
                <p className="text-2xl font-bold text-emerald-600">{totalSpent.toLocaleString()}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {keys.map((key) => {
                const budgetPercent = key.daily_budget > 0
                  ? Math.min((key.spent_today / key.daily_budget) * 100, 100)
                  : 0;

                return (
                  <Card key={key.id} className="kos-card">
                    <div className="card-gradient-top" />
                    <CardHeader className="flex flex-row items-center justify-between">
                      <div>
                        <CardTitle className="text-lg capitalize">{key.provider}</CardTitle>
                        <p className="text-xs text-muted-foreground font-mono mt-1">{key.key_prefix}...</p>
                      </div>
                      <Badge variant={key.is_active ? "default" : "secondary"} className={key.is_active ? "kos-badge-green" : "kos-badge-gray"}>
                        {key.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">User:</span>
                        <span className="font-mono text-xs truncate max-w-[150px]">{key.user_id}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Daily budget:</span>
                        <span>{key.daily_budget.toLocaleString()} tokens</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Spent today:</span>
                        <span>{key.spent_today.toLocaleString()} tokens</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full transition-all"
                          style={{ width: `${budgetPercent}%` }}
                        />
                      </div>
                      <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" size="sm" onClick={() => handleEdit(key)}>
                          <Edit className="h-3 w-3 text-blue-500" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(key.id)}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
              {keys.length === 0 && (
                <p className="text-muted-foreground col-span-2 text-center py-4">No API keys configured yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit API Key</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Active</Label>
              <Switch
                checked={editFormData.is_active}
                onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
              />
            </div>
            <div className="space-y-2">
              <Label>Daily Budget</Label>
              <Input
                type="number"
                value={editFormData.daily_budget}
                onChange={(event) => setEditFormData({ ...editFormData, daily_budget: Number.parseInt(event.target.value, 10) || 0 })}
                className="kos-input"
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
