import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/AuthGuard";
import { YieldContent } from "./YieldContent";

export const metadata: Metadata = {
  title: "Yield outlook",
};

export default function YieldPage() {
  return (
    <AuthGuard>
      <YieldContent />
    </AuthGuard>
  );
}
