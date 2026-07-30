"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { adminApi, type Employee, type EmployeeCreatePayload, type EmployeeUpdatePayload } from "@/lib/api/agentService";
import { toast } from "sonner";
import { Trash2, Edit, UserPlus, Users, UserCheck, UserX, Copy, Download, Ban } from "lucide-react";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";

export default function EmployeesPage() {
  const { t } = useI18n();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editEmployee, setEditEmployee] = useState<Employee | null>(null);
  const [editDesktopInviteLink, setEditDesktopInviteLink] = useState("");
  const [formData, setFormData] = useState<EmployeeCreatePayload>({
    email: "",
    full_name: "",
    department: "",
    role: "employee",
    max_tokens_per_day: 56666666,
    max_requests_per_day: 2000,
  });
  const [editFormData, setEditFormData] = useState<EmployeeUpdatePayload>({
    full_name: "",
    department: "",
    role: "employee",
    is_active: true,
    max_tokens_per_day: 56666666,
    max_requests_per_day: 2000,
  });

  const getDownloadUrl = (platform: "windows" | "mac") => {
    const configured =
      platform === "windows"
        ? process.env.NEXT_PUBLIC_DESKTOP_WINDOWS_DOWNLOAD_URL
        : process.env.NEXT_PUBLIC_DESKTOP_MAC_DOWNLOAD_URL;

    if (configured) {
      return configured;
    }

    const file =
      platform === "windows"
        ? "FQ-SaaS Workspace Setup 1.0.0.exe"
        : "FQ-SaaS Workspace-1.0.0-universal.dmg";

    return `/downloads/${encodeURIComponent(file)}`;
  };

  const load = async () => {
    const response = await adminApi.getEmployees();
    setEmployees(response.data.employees || []);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const response = await adminApi.getEmployees();
      if (!cancelled) {
        setEmployees(response.data.employees || []);
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
      await adminApi.createEmployee(formData);
      toast.success(t("Employee created"));
      setShowDialog(false);
      setFormData({
        email: "",
        full_name: "",
        department: "",
        role: "employee",
        max_tokens_per_day: 56666666,
        max_requests_per_day: 2000,
      });
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to create employee")));
    }
  };

  const buildActivationLink = (inviteToken: string) => {
    if (typeof window === "undefined") return "";
    const fallbackServer = window.location.origin;
    const configuredServer = process.env.NEXT_PUBLIC_API_ORIGIN;
    let server = fallbackServer;

    if (configuredServer) {
      try {
        const parsed = new URL(configuredServer);
        if (!["api", "localhost"].includes(parsed.hostname)) {
          server = configuredServer;
        }
      } catch {
        server = fallbackServer;
      }
    }

    return `fqsaas://activate?server=${encodeURIComponent(server)}&token=${encodeURIComponent(inviteToken)}`;
  };

  const createAndCopyDesktopInvite = async () => {
    if (!editEmployee) return;

    try {
      const response = await adminApi.createDesktopInvite(editEmployee.id);
      const inviteToken = response.data.invite_token;
      const activationLink = response.data.activation_url || buildActivationLink(inviteToken);
      setEditDesktopInviteLink(activationLink);
      await navigator.clipboard.writeText(activationLink);
      toast.success(t("Activation link copied"));
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to create desktop invite")));
    }
  };

  const copyEditDesktopInvite = async () => {
    if (!editDesktopInviteLink) return;
    await navigator.clipboard.writeText(editDesktopInviteLink);
    toast.success(t("Activation link copied"));
  };

  const handleEdit = (employee: Employee) => {
    setEditEmployee(employee);
    setEditFormData({
      full_name: employee.full_name || "",
      department: employee.department || "",
      role: employee.role,
      is_active: employee.is_active,
      max_tokens_per_day: employee.max_tokens_per_day,
      max_requests_per_day: employee.max_requests_per_day,
    });
    setEditDesktopInviteLink("");
    setShowEditDialog(true);
  };

  const handleUpdate = async () => {
    if (!editEmployee) return;

    try {
      await adminApi.updateEmployee(editEmployee.id, editFormData);
      toast.success(t("Employee updated"));
      setShowEditDialog(false);
      setEditEmployee(null);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to update employee")));
    }
  };

  const handleDisable = async (id: string) => {
    if (!confirm(t("Disable this employee?"))) return;

    try {
      await adminApi.disableEmployee(id);
      toast.success(t("Employee disabled"));
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to disable employee")));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t("Delete this employee?"))) return;

    try {
      await adminApi.deleteEmployee(id);
      toast.success(t("Employee deleted"));
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to delete employee")));
    }
  };

  const activeCount = employees.filter((employee) => employee.is_active).length;

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Employees")}</h1>
          <p className="text-muted-foreground mt-1">{t("Manage employee accounts, roles, and daily usage limits.")}</p>
        </div>
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogTrigger asChild>
            <Button className="kos-gradient-btn text-white">
              <UserPlus className="mr-2 h-4 w-4" />
              {t("Add Employee")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("Create Employee")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>{t("Email")}</Label>
                <Input
                  value={formData.email}
                  onChange={(event) => setFormData({ ...formData, email: event.target.value })}
                  placeholder="employee@example.com"
                  className="kos-input"
                />
              </div>
              <div className="space-y-2">
                <Label>{t("Full Name")}</Label>
                <Input
                  value={formData.full_name}
                  onChange={(event) => setFormData({ ...formData, full_name: event.target.value })}
                  className="kos-input"
                />
              </div>
              <div className="space-y-2">
                <Label>{t("Department")}</Label>
                <Input
                  value={formData.department}
                  onChange={(event) => setFormData({ ...formData, department: event.target.value })}
                  placeholder="marketing, hr, sales"
                  className="kos-input"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t("Daily Token Limit")}</Label>
                  <Input
                    type="number"
                    value={formData.max_tokens_per_day}
                    onChange={(event) => setFormData({ ...formData, max_tokens_per_day: Number.parseInt(event.target.value, 10) || 0 })}
                    className="kos-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t("Daily Request Limit")}</Label>
                  <Input
                    type="number"
                    value={formData.max_requests_per_day}
                    onChange={(event) => setFormData({ ...formData, max_requests_per_day: Number.parseInt(event.target.value, 10) || 0 })}
                    className="kos-input"
                  />
                </div>
              </div>
              <Button className="w-full kos-gradient-btn text-white" onClick={handleCreate}>
                {t("Create Employee")}
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
                <p className="text-sm text-muted-foreground">{t("Total Employees")}</p>
                <p className="text-2xl font-bold">{employees.length}</p>
              </div>
              <Users className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #10B981, #059669)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Active")}</p>
                <p className="text-2xl font-bold text-emerald-600">{activeCount}</p>
              </div>
              <UserCheck className="h-8 w-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="kos-card">
          <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #EF4444, #DC2626)" }} />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t("Disabled")}</p>
                <p className="text-2xl font-bold text-red-600">{employees.length - activeCount}</p>
              </div>
              <UserX className="h-8 w-8 text-red-600" />
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
                  <TableHead>{t("Name")}</TableHead>
                  <TableHead>{t("Email")}</TableHead>
                  <TableHead>{t("Department")}</TableHead>
                  <TableHead>{t("Role")}</TableHead>
                  <TableHead>{t("Status")}</TableHead>
                  <TableHead>{t("Limits")}</TableHead>
                  <TableHead className="text-right">{t("Actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map((employee) => (
                  <TableRow key={employee.id}>
                    <TableCell className="font-medium">{employee.full_name || "-"}</TableCell>
                    <TableCell className="text-sm">{employee.email}</TableCell>
                    <TableCell>{employee.department || "-"}</TableCell>
                    <TableCell>
                      <Badge variant={employee.role === "admin" ? "default" : "secondary"}>{t(employee.role)}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={employee.is_active ? "default" : "destructive"}
                        className={employee.is_active ? "kos-badge-green" : "kos-badge-red"}
                      >
                        {employee.is_active ? t("Active") : t("Disabled")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      {employee.max_tokens_per_day.toLocaleString()} {t("tok")} / {employee.max_requests_per_day} {t("req")}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(employee)}>
                          <Edit className="h-4 w-4 text-blue-500" />
                        </Button>
                        <Button aria-label={t("Disable")} title={t("Disable")} variant="ghost" size="sm" onClick={() => handleDisable(employee.id)} disabled={!employee.is_active}>
                          <Ban className="h-4 w-4 text-amber-500" />
                        </Button>
                        <Button aria-label={t("Delete")} title={t("Delete")} variant="ghost" size="sm" onClick={() => handleDelete(employee.id)}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {employees.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      {t("No employees found.")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="kos-card">
        <CardContent className="pt-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold">{t("Desktop app downloads")}</p>
              <p className="text-sm text-muted-foreground">{t("The installer is shared by all employees. Activation is employee-specific.")}</p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Button type="button" variant="outline" asChild>
                <a href={getDownloadUrl("windows")} download>
                  <Download className="mr-2 h-4 w-4" />
                  {t("Download Windows app")}
                </a>
              </Button>
              <Button type="button" variant="outline" asChild>
                <a href={getDownloadUrl("mac")} download>
                  <Download className="mr-2 h-4 w-4" />
                  {t("Download macOS app")}
                </a>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("Edit Employee")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t("Full Name")}</Label>
              <Input
                value={editFormData.full_name}
                onChange={(event) => setEditFormData({ ...editFormData, full_name: event.target.value })}
                className="kos-input"
              />
            </div>
            <div className="space-y-2">
              <Label>{t("Department")}</Label>
              <Input
                value={editFormData.department}
                onChange={(event) => setEditFormData({ ...editFormData, department: event.target.value })}
                placeholder="marketing, hr, sales"
                className="kos-input"
              />
            </div>
            <div className="space-y-2">
              <Label>{t("Role")}</Label>
              <select
                className="w-full p-2 border rounded-md text-sm kos-input"
                value={editFormData.role}
                onChange={(event) => setEditFormData({ ...editFormData, role: event.target.value })}
              >
                <option value="employee">{t("employee")}</option>
                <option value="admin">{t("admin")}</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <Label>{t("Active")}</Label>
              <Switch
                checked={editFormData.is_active}
                onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t("Daily Token Limit")}</Label>
                <Input
                  type="number"
                  value={editFormData.max_tokens_per_day}
                  onChange={(event) => setEditFormData({ ...editFormData, max_tokens_per_day: Number.parseInt(event.target.value, 10) || 0 })}
                  className="kos-input"
                />
              </div>
              <div className="space-y-2">
                <Label>{t("Daily Request Limit")}</Label>
                <Input
                  type="number"
                  value={editFormData.max_requests_per_day}
                  onChange={(event) => setEditFormData({ ...editFormData, max_requests_per_day: Number.parseInt(event.target.value, 10) || 0 })}
                  className="kos-input"
                />
              </div>
            </div>
            <Button className="w-full kos-gradient-btn text-white" onClick={handleUpdate}>
              {t("Save Changes")}
            </Button>
            <div className="space-y-2 rounded-md border p-3">
              <Label>{t("Employee desktop activation")}</Label>
              {editEmployee?.is_activated && (
                <p className="text-sm text-muted-foreground">
                  {t("Reissuing the activation link signs the employee out of existing desktop sessions.")}
                </p>
              )}
              <Button type="button" className="w-full" variant="secondary" onClick={createAndCopyDesktopInvite}>
                <Copy className="mr-2 h-4 w-4" />
                {editEmployee?.is_activated
                  ? t("Reissue and copy desktop activation link")
                  : editEmployee?.has_invite_token
                    ? t("Copy desktop activation link")
                    : t("Create and copy desktop activation link")}
              </Button>
              {editDesktopInviteLink && (
                <div className="flex gap-2">
                  <Input value={editDesktopInviteLink} readOnly className="kos-input text-xs" />
                  <Button type="button" variant="outline" size="icon" onClick={copyEditDesktopInvite}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
