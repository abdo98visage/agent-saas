"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { adminApi, type AdminAgentTestResponse, type Profile } from "@/lib/api/agentService";
import { getErrorMessage } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n";
import { toast } from "sonner";
import { Bot, Send, FlaskConical, Clock3, Coins, Cable, DatabaseZap } from "lucide-react";

type ChatEntry =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; meta: AdminAgentTestResponse };

export default function AgentTestPage() {
  const { t, safeText } = useI18n();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [message, setMessage] = useState("اعطني ردا قصيرا يثبت انك تعمل فعليا واذكر بإيجاز مهمتك.");
  const [projectContext, setProjectContext] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [isPending, startTransition] = useTransition();
  const selectedProfileRef = useRef("");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await adminApi.getProfiles();
        if (cancelled) {
          return;
        }
        const activeProfiles = (response.data.profiles || []).filter((profile: Profile) => profile.is_active);
        setProfiles(activeProfiles);
        if (!selectedProfileRef.current && activeProfiles.length > 0) {
          selectedProfileRef.current = activeProfiles[0].name;
          setSelectedProfile(activeProfiles[0].name);
        }
      } catch (error: unknown) {
        if (!cancelled) {
          toast.error(getErrorMessage(error, "Failed to load profiles"));
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProfileObject = profiles.find((profile) => profile.name === selectedProfile) || null;

  const resetConversation = () => {
    setConversationId(null);
    setEntries([]);
  };

  const sendMessage = () => {
    const trimmed = message.trim();
    const currentSelectedProfile = selectedProfileRef.current || selectedProfile;
    const currentSelectedProfileObject = profiles.find((profile) => profile.name === currentSelectedProfile) || null;

    if (!trimmed || !currentSelectedProfile) {
      return;
    }

    const userEntry: ChatEntry = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    setEntries((current) => [...current, userEntry]);
    setMessage("");

    startTransition(async () => {
      try {
        const response = await adminApi.testAgentMessage({
          message: trimmed,
          profile_name: currentSelectedProfile,
          conversation_id: conversationId,
          agent_template_name: "default",
          project_context: projectContext.trim() || undefined,
        });

        const data = response.data;
        setConversationId(data.conversation_id || null);
        setEntries((current) => [
          ...current,
          {
            id: data.message_id || `assistant-${Date.now()}`,
            role: "assistant",
            content: data.content,
            meta: data,
          },
        ]);
      } catch (error: unknown) {
        const errorMessage = getErrorMessage(error, "Agent test failed");
        toast.error(errorMessage);
        setEntries((current) => [
          ...current,
          {
            id: `assistant-error-${Date.now()}`,
            role: "assistant",
            content: `Test failed: ${errorMessage}`,
            meta: {
              conversation_id: conversationId,
              message_id: null,
              content: "",
              tokens_used: null,
              input_tokens: null,
              output_tokens: null,
              total_tokens: null,
              latency_ms: null,
              model: null,
              provider: null,
              runtime_type: null,
              request_url: null,
              profile_name: currentSelectedProfile,
              profile_id: currentSelectedProfileObject?.id || null,
              total_cost: null,
              pricing_snapshot: null,
            },
          },
        ]);
      }
    });
  };

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">{t("Agent Tester")}</h1>
          <p className="text-muted-foreground mt-1">
            {t("Test any agent from inside the platform and verify the real response and execution details.")}
          </p>
        </div>
        <Button variant="outline" onClick={resetConversation}>
          {t("New Test Chat")}
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px,1fr]">
        <Card className="kos-card h-fit">
          <div className="card-gradient-top" />
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="h-5 w-5 text-indigo-600" />
              {t("Test Controls")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t("Agent / Profile")}</Label>
              <select
                className="w-full p-2 border rounded-xl text-sm kos-input"
                value={selectedProfile}
                onChange={(event) => {
                  selectedProfileRef.current = event.target.value;
                  setSelectedProfile(event.target.value);
                  setConversationId(null);
                  setEntries([]);
                }}
              >
                <option value="">Select profile</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.name}>
                    {safeText(profile.name)} ({safeText(profile.slug)})
                  </option>
                ))}
              </select>
              {selectedProfileObject && (
                <div className="flex flex-wrap gap-2 pt-1">
                  <Badge variant="outline">{t(selectedProfileObject.runtime_type === "direct_llm" ? "Direct Model" : "Smart Agents")}</Badge>
                  <Badge
                    variant="outline"
                    className={selectedProfileObject.hermes_sync_status === "synced" ? "text-emerald-700" : "text-amber-700"}
                  >
                    {t(selectedProfileObject.hermes_sync_status || "pending")}
                  </Badge>
                  <Badge variant="outline">
                    {t("providers:")} {(selectedProfileObject.allowed_providers || []).join(", ") || "any"}
                  </Badge>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>{t("Optional Project Context")}</Label>
              <textarea
                className="w-full min-h-[120px] p-3 border rounded-xl text-sm bg-gray-50"
                value={projectContext}
                onChange={(event) => setProjectContext(event.target.value)}
                placeholder={t("Optional context sent with this test message.")}
              />
            </div>

            <div className="space-y-2">
              <Label>Message</Label>
              <textarea
                className="w-full min-h-[160px] p-3 border rounded-xl text-sm bg-gray-50"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={t("Write the admin test message here.")}
              />
            </div>

            <Button className="w-full kos-gradient-btn text-white" onClick={sendMessage} disabled={isPending || !selectedProfile || !message.trim()}>
              <Send className="mr-2 h-4 w-4" />
              {isPending ? t("Testing agent...") : t("Send Test Message")}
            </Button>

            <div className="rounded-xl border border-gray-100 bg-gray-50 p-3 text-sm">
              <div className="font-medium">{t("Current conversation")}</div>
              <div className="text-muted-foreground break-all">{conversationId || t("No active conversation yet.")}</div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {entries.length === 0 ? (
            <Card className="kos-card">
              <CardContent className="py-16 text-center text-muted-foreground">
                {t("Choose an agent, then send a test message. Each reply will show the real content along with the model, URL, tokens, and cost.")}
              </CardContent>
            </Card>
          ) : (
            entries.map((entry) => (
              <Card key={entry.id} className="kos-card overflow-hidden">
                <div
                  className="card-gradient-top"
                  style={{
                    background:
                      entry.role === "user"
                        ? "linear-gradient(90deg, #2563EB, #4F46E5)"
                        : "linear-gradient(90deg, #059669, #10B981)",
                  }}
                />
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center gap-2">
                    {entry.role === "user" ? (
                      <>
                        <Send className="h-4 w-4 text-indigo-600" />
                        <span className="font-semibold">Admin message</span>
                      </>
                    ) : (
                      <>
                        <Bot className="h-4 w-4 text-emerald-600" />
                        <span className="font-semibold">Agent response</span>
                      </>
                    )}
                  </div>

                  <div className="whitespace-pre-wrap rounded-xl border border-gray-100 bg-gray-50 p-4 text-sm leading-7">
                    {entry.content}
                  </div>

                  {entry.role === "assistant" && (
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 text-sm">
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground flex items-center gap-2"><DatabaseZap className="h-4 w-4" /> Model</div>
                        <div className="font-semibold break-all">{entry.meta.model || "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground flex items-center gap-2"><Cable className="h-4 w-4" /> Provider / Runtime</div>
                        <div className="font-semibold break-all">{entry.meta.provider || "n/a"} / {entry.meta.runtime_type || "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground flex items-center gap-2"><Clock3 className="h-4 w-4" /> Latency</div>
                        <div className="font-semibold">{entry.meta.latency_ms ?? "n/a"} ms</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3 xl:col-span-2">
                        <div className="text-muted-foreground">Request URL</div>
                        <div className="font-semibold break-all">{entry.meta.request_url || "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground flex items-center gap-2"><Coins className="h-4 w-4" /> Cost</div>
                        <div className="font-semibold">${typeof entry.meta.total_cost === "number" ? entry.meta.total_cost.toFixed(6) : "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground">Input Tokens</div>
                        <div className="font-semibold">{entry.meta.input_tokens ?? "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground">Output Tokens</div>
                        <div className="font-semibold">{entry.meta.output_tokens ?? "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3">
                        <div className="text-muted-foreground">Total Tokens</div>
                        <div className="font-semibold">{entry.meta.total_tokens ?? entry.meta.tokens_used ?? "n/a"}</div>
                      </div>
                      <div className="rounded-xl border bg-white p-3 xl:col-span-3">
                        <div className="text-muted-foreground">Profile Used</div>
                        <div className="font-semibold">{entry.meta.profile_name || "n/a"}</div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
