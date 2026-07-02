"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import apiClient from "@/lib/api/client";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname === "/login") {
      return;
    }

    let cancelled = false;

    apiClient.get("/auth/me").catch((error: { response?: { status?: number } }) => {
      if (!cancelled && error?.response?.status === 401) {
        router.push("/login");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return <>{children}</>;
}
