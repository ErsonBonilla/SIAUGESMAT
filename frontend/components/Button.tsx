import type { ComponentChildren } from "preact";
import { SpinnerIcon } from "../utils/icons.tsx";

interface ButtonProps {
  variant?: "primary" | "secondary" | "ghost" | "green" | "gradient";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  disabled?: boolean;
  children: ComponentChildren;
  class?: string;
  type?: "button" | "submit" | "reset";
  onClick?: (e: MouseEvent) => void;
  style?: Record<string, string>;
}

const variantClasses: Record<string, string> = {
  primary:
    "bg-[var(--accent)] text-white rounded-lg px-4 py-2.5 text-sm hover:brightness-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--accent-rgb),0.4)]",
  secondary:
    "bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-secondary)] rounded-lg px-4 py-2.5 text-sm hover:bg-[var(--bg-tertiary)]",
  ghost: "bg-transparent gradient-text p-0 text-sm hover:underline",
  green:
    "bg-[var(--brand-green)] text-white rounded-lg px-4 py-2.5 text-sm hover:bg-[var(--brand-green-dark)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--brand-green-rgb),0.4)]",
  gradient:
    "bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white rounded-lg px-4 py-2.5 text-sm hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--brand-green-rgb),0.4)]",
};

const sizeClasses: Record<string, string> = {
  sm: "px-3 py-1 text-xs rounded-md",
  md: "",
  lg: "px-6 py-3 text-base",
};

export default function Button(
  {
    variant = "primary",
    size = "md",
    loading,
    disabled,
    children,
    class: extraClass,
    type = "button",
    onClick,
    style,
  }: ButtonProps,
) {
  const cls = [
    "inline-flex items-center justify-center gap-2 border-0 cursor-pointer font-inherit transition-all duration-200 font-medium no-underline leading-5 disabled:opacity-60 disabled:cursor-not-allowed disabled:pointer-events-none",
    variantClasses[variant],
    sizeClasses[size],
    extraClass ?? "",
  ].filter(Boolean).join(" ");

  return (
    <button
      type={type}
      class={cls}
      disabled={disabled || loading}
      onClick={onClick}
      style={style}
    >
      {loading && (
        <SpinnerIcon
          style={{ width: "1.25rem", height: "1.25rem" }}
          class="animate-spin shrink-0"
        />
      )}
      {children}
    </button>
  );
}
