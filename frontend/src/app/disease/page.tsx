import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/AuthGuard";

import { DiseaseContent } from "./DiseaseContent";

export const metadata: Metadata = {
  title: "Check a leaf",
};

export default function DiseasePage() {
  return (
    <AuthGuard>
      <DiseaseContent />
    </AuthGuard>
  );
}
