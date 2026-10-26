"use client";

/**
 * Gate for authenticated-only pages (/disease, /yield, /dashboard).
 *
 * Anonymous visitors are redirected to /login with a `next` parameter so they
 * land back where they intended after signing in. While the session is being
 * resolved (or redirected away) a quiet spinner keeps the layout stable.
 */

import { useEffect } from "react";
import type { ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { ThemedLoader } from "@/components/ui/ThemedLoader";

import { useAuth } from "./AuthProvider";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, pathname, router]);

  if (status === "authenticated") {
    return <>{children}</>;
  }

  return <ThemedLoader label="Checking your session" className="min-h-[28rem]" size="md" />;
}
