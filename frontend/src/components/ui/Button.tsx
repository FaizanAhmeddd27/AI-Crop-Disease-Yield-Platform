import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost";
type Size = "md" | "lg";

const base =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-medium transition-colors " +
  "disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 " +
  "focus-visible:outline-offset-2 focus-visible:outline-forest";

const variants: Record<Variant, string> = {
  // docs/DESIGN.md: forest fill, leaf text; hover inverts to leaf fill, forest text.
  primary:
    "bg-forest text-leaf ring-1 ring-forest hover:bg-leaf hover:text-forest hover:ring-forest",
  ghost:
    "border border-forest bg-transparent text-forest hover:bg-surface hover:text-ink",
  secondary:
    "border border-border-subtle bg-surface text-ink hover:bg-surface-muted",
};

// 44 px minimum height on the default size (NFR-U-004).
const sizes: Record<Size, string> = {
  md: "min-h-11 px-4 text-sm",
  lg: "min-h-12 px-6 text-base",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", className?: string) {
  return cn(base, variants[variant], sizes[size], className);
}

interface ButtonProps extends ComponentProps<"button"> {
  variant?: Variant;
  size?: Size;
}

export function Button({ variant = "primary", size = "md", className, ...props }: ButtonProps) {
  return <button className={buttonClass(variant, size, className)} {...props} />;
}

interface ButtonLinkProps extends Omit<ComponentProps<typeof Link>, "className"> {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...props}>
      {children}
    </Link>
  );
}
