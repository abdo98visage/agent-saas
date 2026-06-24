"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/api/agentService";
import { toast } from "sonner";
import { Zap, Mail, Lock } from "lucide-react";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { t } = useI18n();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);

    try {
      await authApi.login(email, password);
      toast.success(t("Signed in"));
      router.push("/");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("Failed to sign in")));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-indigo-50/30 to-purple-50/20 p-4">
      <div className="relative z-10 w-full max-w-md">
        <div className="text-center mb-8 kos-animate-in">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 text-white mb-4 shadow-xl shadow-indigo-200">
            <span className="text-3xl font-bold">K</span>
          </div>
          <h1 className="text-3xl font-bold kos-gradient-text mb-1">KarzounOS</h1>
          <p className="text-sm text-muted-foreground">{t("Admin access")}</p>
        </div>

        <Card className="kos-card kos-animate-in border-0 shadow-xl">
          <div className="card-gradient-top" />
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl text-center font-bold">{t("Sign In")}</CardTitle>
            <CardDescription className="text-center">{t("Use your admin credentials to open the dashboard.")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="flex items-center gap-2">
                  <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                  {t("Email")}
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="admin@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  className="kos-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="flex items-center gap-2">
                  <Lock className="h-3.5 w-3.5 text-muted-foreground" />
                  {t("Password")}
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  className="kos-input"
                />
              </div>
              <Button type="submit" className="w-full kos-gradient-btn text-white font-semibold" disabled={loading}>
                {loading ? (
                  <span className="flex items-center gap-2">
                    <Zap className="h-4 w-4 animate-spin" />
                    {t("Signing in...")}
                  </span>
                ) : (
                  t("Sign In")
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
