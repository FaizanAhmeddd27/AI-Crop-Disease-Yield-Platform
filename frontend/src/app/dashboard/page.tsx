import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/AuthGuard";

import { DashboardContent } from "./DashboardContent";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}
