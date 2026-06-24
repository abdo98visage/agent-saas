"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import apiClient from "@/lib/api/client";
import { useI18n } from "@/lib/i18n";
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Bot,
  Wrench,
  MessageSquare,
  Key,
  Plug,
  Shield,
  LogOut,
  Menu,
  BookOpen,
  ServerCog,
  FlaskConical,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/employees", label: "Employees", icon: Users },
  { href: "/profiles", label: "Profiles", icon: Bot },
  { href: "/skills", label: "Skills", icon: Wrench },
  { href: "/assignments", label: "Assignments", icon: Plug },
  { href: "/sessions", label: "Sessions", icon: MessageSquare },
  { href: "/kpis", label: "KPIs", icon: BarChart3 },
  { href: "/api-keys", label: "API Keys", icon: Key },
  { href: "/agent-test", label: "Agent Tester", icon: FlaskConical },
  { href: "/hermes", label: "Hermes Runtime", icon: ServerCog },
  { href: "/audit", label: "Audit Log", icon: Shield },
  { href: "/templates", label: "Templates", icon: BookOpen },
];

function SidebarContent() {
  const pathname = usePathname();
  const { language, t, setLanguage } = useI18n();

  const handleLogout = async () => {
    try {
      await apiClient.post("/auth/logout");
    } finally {
      window.location.href = "/login";
    }
  };

  return (
    <>
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-indigo-200">
            K
          </div>
          <div>
            <h1 className="text-lg font-bold kos-gradient-text">KarzounOS</h1>
            <p className="text-[10px] text-muted-foreground font-medium">{t("Admin dashboard")}</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto py-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <div className={cn("kos-sidebar-item", isActive && "active")}>
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span className="truncate">{t(item.label)}</span>
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-2 mx-3 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-100">
        <div className="flex items-center gap-2 text-emerald-700">
          <div className="kos-online-pulse" />
          <span className="text-xs font-semibold">{t("Workspace connected")}</span>
        </div>
      </div>

      <div className="p-3 border-t border-gray-100 mt-2">
        <div className="flex items-center gap-2">
          <Button variant="outline" className="flex-1" onClick={() => setLanguage(language === "ar" ? "en" : "ar")}>
            {language === "ar" ? "English" : t("Arabic")}
          </Button>
          <Button
            variant="ghost"
            className="flex-1 justify-start gap-2 text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />
            <span className="text-sm font-medium">{t("Sign Out")}</span>
          </Button>
        </div>
      </div>
    </>
  );
}

export function Sidebar() {
  const { dir } = useI18n();

  return (
    <>
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white/80 backdrop-blur-lg border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">
            K
          </div>
          <span className="font-bold text-sm kos-gradient-text">KarzounOS</span>
        </div>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side={dir === "rtl" ? "right" : "left"} className="w-72 p-0">
            <SidebarContent />
          </SheetContent>
        </Sheet>
      </div>

      <div className="hidden md:flex kos-sidebar">
        <SidebarContent />
      </div>
    </>
  );
}
