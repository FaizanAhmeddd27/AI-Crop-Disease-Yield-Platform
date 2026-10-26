import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthPanel } from "@/components/auth/AuthPanel";

export const metadata: Metadata = {
  title: "Log in or register",
};

export default function LoginPage() {
  return (
    <div className="py-2 sm:py-6">
      <Suspense fallback={<div aria-hidden="true" className="min-h-[36rem]" />}>
        <AuthPanel />
      </Suspense>
    </div>
  );
}
