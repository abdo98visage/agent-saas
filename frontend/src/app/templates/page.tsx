"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { adminApi, type AgentTemplate, type AgentTool } from "@/lib/api/agentService";
import { BookOpen } from "lucide-react";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const response = await adminApi.getTemplates();
      if (!cancelled) {
        setTemplates(response.data.templates || []);
        setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="p-8 space-y-6 kos-animate-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">Agent Templates</h1>
        <p className="text-muted-foreground mt-1">Reusable model and tool presets for future agents.</p>
      </div>

      <Card className="kos-card">
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {templates.map((template) => (
                <Card key={template.name} className="kos-card">
                  <div className="card-gradient-top" />
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-lg">{template.name}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-1">{template.department || "General"}</p>
                    </div>
                    <Badge variant="secondary" className="kos-badge-purple">{template.model_name}</Badge>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div>
                      <span className="text-xs text-muted-foreground">Tools:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(template.tools || []).map((tool: string | AgentTool, index: number) => (
                          <Badge key={`${template.name}-${index}`} variant="outline" className="text-xs">
                            {typeof tool === "string" ? tool : tool.name || "tool"}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Temperature:</span>
                      <span>{template.temperature}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {templates.length === 0 && (
                <p className="text-muted-foreground col-span-2 text-center py-4 flex items-center justify-center gap-2">
                  <BookOpen className="h-4 w-4" />
                  No templates configured yet.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
