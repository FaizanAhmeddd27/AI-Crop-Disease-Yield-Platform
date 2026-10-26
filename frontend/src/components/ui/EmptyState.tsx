import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

/** Consistent placeholder for "no result yet" states across pages. */
export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3 rounded-lg border border-dashed border-border-subtle p-6",
        className,
      )}
    >
      <p className="font-medium text-ink">{title}</p>
      <p className="text-sm text-ink-muted">{description}</p>
      {action}
    </div>
  );
}
