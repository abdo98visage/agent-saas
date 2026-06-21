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
import { adminApi, type ProviderPricing } from "@/lib/api/agentService";

interface ApiKey {
  id: string;
  owner_type: "user" | "profile" | "platform";
  user_id: string | null;
  profile_id: string | null;
  provider: string;
  key_prefix: string;
  is_active: boolean;
  daily_budget: number;
  spent_today: number;
}

interface EmployeeOption {
  id: string;
  email: string;
  full_name: string | null;
}

interface ProfileOption {
  id: string;
  name: string;
  slug: string;
  hermes_sync_status?: string;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [profiles, setProfiles] = useState<ProfileOption[]>([]);
  const [pricing, setPricing] = useState<ProviderPricing | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editKey, setEditKey] = useState<ApiKey | null>(null);
  const [formData, setFormData] = useState({
    owner_type: "profile" as "user" | "profile" | "platform",
    user_id: "",
    profile_id: "",
    provider: "minimax",
    api_key: "",
    daily_budget: 50000,
  });
  const [editFormData, setEditFormData] = useState({
    is_active: true,
    daily_budget: 50000,
  });
  const [pricingForm, setPricingForm] = useState({
    monthly_price_usd: 20,
    monthly_token_allowance: 1_700_000_000,
    currency: "USD",
  });

  const load = async () => {
    const [keysResponse, employeesResponse, profilesResponse, pricingResponse] = await Promise.all([
      apiClient.get("/admin/api-keys"),
      apiClient.get("/admin/employees"),
      apiClient.get("/admin/profiles"),
      adminApi.getProviderPricing({ provider: "minimax" }),
    ]);
    setKeys(keysResponse.data.api_keys || []);
    setEmployees(employeesResponse.data.employees || []);
    setProfiles(profilesResponse.data.profiles || []);
    const activePricing = (pricingResponse.data.pricing || []).find((item: ProviderPricing) => item.is_active) || null;
    setPricing(activePricing);
    if (activePricing) {
      setPricingForm({
        monthly_price_usd: activePricing.monthly_price_usd,
        monthly_token_allowance: activePricing.monthly_token_allowance,
        currency: activePricing.currency,
      });
    }
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const [keysResponse, employeesResponse, profilesResponse, pricingResponse] = await Promise.all([
        apiClient.get("/admin/api-keys"),
        apiClient.get("/admin/employees"),
        apiClient.get("/admin/profiles"),
        adminApi.getProviderPricing({ provider: "minimax" }),
      ]);
      if (!cancelled) {
        setKeys(keysResponse.data.api_keys || []);
        setEmployees(employeesResponse.data.employees || []);
        setProfiles(profilesResponse.data.profiles || []);
        const activePricing = (pricingResponse.data.pricing || []).find((item: ProviderPricing) => item.is_active) || null;
        setPricing(activePricing);
        if (activePricing) {
          setPricingForm({
            monthly_price_usd: activePricing.monthly_price_usd,
            monthly_token_allowance: activePricing.monthly_token_allowance,
            currency: activePricing.currency,
          });
        }
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
      await apiClient.post("/admin/api-keys", {
        owner_type: formData.owner_type,
        user_id: formData.owner_type === "user" ? formData.user_id : null,
        profile_id: formData.owner_type === "profile" ? formData.profile_id : null,
        provider: formData.provider,
        api_key: formData.api_key,
        daily_budget: formData.daily_budget,
      });
      toast.success("API key created");
      setShowDialog(false);
      setFormData({ owner_type: "profile", user_id: "", profile_id: "", provider: "minimax", api_key: "", daily_budget: 50000 });
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

  const handlePricingSave = async () => {
    try {
      await adminApi.updateProviderPricing("minimax", pricingForm);
      toast.success("MiniMax pricing updated");
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to update pricing"));
    }
  };

  const totalBudget = keys.reduce((sum, key) => sum + key.daily_budget, 0);
  const totalSpent = keys.reduce((sum, key) => sum + key.spent_today, 0);

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">API Keys</h1>
          <p className="text-muted-foreground mt-1">Manage profile, employee override, and platform provider credentials.</p>
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
                <Label>Owner Type</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.owner_type}
                  onChange={(event) => setFormData({ ...formData, owner_type: event.target.value as "user" | "profile" | "platform" })}
                >
                  <option value="profile">Profile key</option>
                  <option value="user">Employee override key</option>
                  <option value="platform">Platform fallback key</option>
                </select>
              </div>
              {formData.owner_type === "user" && (
              <div className="space-y-2">
                <Label>Employee</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.user_id}
                  onChange={(event) => setFormData({ ...formData, user_id: event.target.value })}
                >
                  <option value="">Select employee</option>
                  {employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.full_name || employee.email} ({employee.email})
                    </option>
                  ))}
                </select>
              </div>
              )}
              {formData.owner_type === "profile" && (
              <div className="space-y-2">
                <Label>Profile</Label>
                <select
                  className="w-full p-2 border rounded-xl text-sm kos-input"
                  value={formData.profile_id}
                  onChange={(event) => setFormData({ ...formData, profile_id: event.target.value })}
                >
                  <option value="">Select profile</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name} ({profile.slug}) - {profile.hermes_sync_status || "pending"}
                    </option>
                  ))}
                </select>
              </div>
              )}
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
        <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #0F766E, #0EA5A4)" }} />
        <CardHeader>
          <CardTitle>MiniMax Monthly Pricing Model</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-4">
          <div className="space-y-2">
            <Label>Monthly Price (USD)</Label>
            <Input
              type="number"
              step="0.01"
              value={pricingForm.monthly_price_usd}
              onChange={(event) => setPricingForm({ ...pricingForm, monthly_price_usd: Number.parseFloat(event.target.value) || 0 })}
              className="kos-input"
            />
          </div>
          <div className="space-y-2">
            <Label>Monthly Token Allowance</Label>
            <Input
              type="number"
              value={pricingForm.monthly_token_allowance}
              onChange={(event) => setPricingForm({ ...pricingForm, monthly_token_allowance: Number.parseInt(event.target.value, 10) || 0 })}
              className="kos-input"
            />
          </div>
          <div className="space-y-2">
            <Label>Currency</Label>
            <Input
              value={pricingForm.currency}
              onChange={(event) => setPricingForm({ ...pricingForm, currency: event.target.value.toUpperCase() })}
              className="kos-input"
            />
          </div>
          <div className="flex items-end">
            <Button className="w-full kos-gradient-btn text-white" onClick={() => void handlePricingSave()}>
              Save Pricing
            </Button>
          </div>
          <div className="md:col-span-4 text-sm text-muted-foreground">
            Current rate: {pricing ? `${pricing.usd_per_1m_tokens.toFixed(4)} USD per 1M tokens` : "No active pricing configured yet."}
          </div>
        </CardContent>
      </Card>

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
                        <Badge variant="outline" className="mt-2 capitalize">{key.owner_type}</Badge>
                      </div>
                      <Badge variant={key.is_active ? "default" : "secondary"} className={key.is_active ? "kos-badge-green" : "kos-badge-gray"}>
                        {key.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Owner:</span>
                        <span className="font-mono text-xs truncate max-w-[180px]">
                          {key.owner_type === "profile" ? key.profile_id : key.owner_type === "user" ? key.user_id : "platform"}
                        </span>
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
