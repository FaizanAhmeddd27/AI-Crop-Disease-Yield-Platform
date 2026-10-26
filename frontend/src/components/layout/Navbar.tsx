"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { buttonClass } from "@/components/ui/Button";
import { ThemedLoader } from "@/components/ui/ThemedLoader";
import { cn } from "@/lib/utils";

export function Navbar() {
  const pathname = usePathname();
  const auth = useAuth();
  const isAuthPage = pathname.startsWith("/login");

  // In dashboard page, navbar is hidden; dashboard provides its own header with logout
  if (pathname.startsWith("/dashboard")) {
    return null;
  }

  return (
    <header className="sticky top-3 z-50 px-3 sm:px-4">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-6xl items-center justify-between gap-2 rounded-full border border-hairline bg-surface/85 py-2 pl-2 pr-2 shadow-[0_2px_16px_rgba(6,71,52,0.10)] backdrop-blur-md sm:pl-3"
      >
        <Link
          href="/"
          className="flex shrink-0 items-center"
          aria-label="Zenvy home"
        >
          <Image
            src="/logo.png"
            alt="Zenvy"
            width={410}
            height={406}
            className="h-12 w-auto object-contain sm:h-14"
            sizes="56px"
            priority
          />
        </Link>

        <div className="flex items-center gap-1 overflow-x-auto sm:gap-1.5">
          <Link
            href="/about"
            aria-current={pathname.startsWith("/about") ? "page" : undefined}
            className={cn(
              "shrink-0 rounded-full px-3 py-1.5 text-sm transition-colors",
              pathname.startsWith("/about")
                ? "bg-brand-100 font-medium text-forest"
                : "text-ink-muted hover:bg-page hover:text-forest",
            )}
          >
            About
          </Link>

          {/* Session state drives the right side:
              logged out → Log in + Register · logged in → Dashboard + Log out */}
          {auth.status === "loading" && (
            <ThemedLoader label="" size="sm" className="ml-1 h-9 w-10 rounded-full bg-brand-100/70" />
          )}

          {auth.status === "anonymous" && (
            <>
              <Link
                href="/login"
                aria-current={isAuthPage ? "page" : undefined}
                className={cn(
                  buttonClass("ghost", "md", "rounded-full px-4 py-1.5 min-h-9 shrink-0"),
                )}
              >
                Log in
              </Link>
              <Link
                href="/login?mode=register"
                className={cn(
                  buttonClass("primary", "md", "rounded-full px-4 py-1.5 min-h-9 shrink-0"),
                )}
              >
                Register
              </Link>
            </>
          )}

          {auth.status === "authenticated" && (
            <>
              <Link
                href="/dashboard"
                aria-current={pathname.startsWith("/dashboard") ? "page" : undefined}
                className={cn(
                  buttonClass("primary", "md", "rounded-full px-4 py-1.5 min-h-9 shrink-0"),
                )}
              >
                Dashboard
              </Link>
              <button
                type="button"
                onClick={() => auth.logout()}
                className={cn(
                  buttonClass("ghost", "md", "rounded-full px-3.5 py-1.5 min-h-9 shrink-0 text-ink-muted hover:text-forest hover:bg-page"),
                )}
              >
                Log out
              </button>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
