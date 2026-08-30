import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger";
}

const VARIANTS: Record<string, string> = {
  primary: "bg-brass text-ink hover:bg-brass-bright",
  ghost: "border border-border text-ink-50 hover:bg-surface2",
  danger: "border border-blocked/40 text-blocked hover:bg-blocked/10",
};

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`px-3.5 py-2 rounded-sm text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
