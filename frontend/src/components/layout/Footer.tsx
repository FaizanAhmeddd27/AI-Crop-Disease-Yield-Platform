"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { copy } from "@/lib/copy";

export function Footer() {
  const pathname = usePathname();
  if (pathname.startsWith("/dashboard")) {
    return null;
  }
  const strings = copy.en;
  return (
    <footer className="mt-16 border-t border-hairline">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-prose">
          <strong className="font-medium text-ink">{strings.disclaimer.title}</strong>{" "}
          {strings.disclaimer.body}
        </p>
        <nav aria-label="Footer" className="flex gap-4">
          <Link href="/about" className="hover:text-forest hover:underline">
            {strings.navigation.aboutModels}
          </Link>
          <a
            href="https://open-meteo.com/"
            className="hover:text-forest hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {strings.navigation.weatherData}
          </a>
        </nav>
      </div>
    </footer>
  );
}
