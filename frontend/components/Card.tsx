import type { ComponentChildren } from "preact";

type CardProps = {
  variant?: "default" | "glass";
  hover?: boolean;
  padding?: "sm" | "md" | "lg";
  class?: string;
  style?: Record<string, string>;
  children: ComponentChildren;
} & ({ as?: "div"; href?: never } | { as: "a"; href: string });

export default function Card(
  {
    variant = "default",
    hover,
    padding = "md",
    class: extraClass,
    style,
    children,
    as = "div",
    href,
  }: CardProps,
) {
  const base = "rounded-xl border p-6";
  const defaultStyle =
    "bg-[var(--bg-primary)] border-[var(--border-primary)] shadow-[0_1px_2px_rgba(0,0,0,0.06),0_1px_3px_rgba(0,0,0,0.04)] active:ring-2 active:ring-[var(--accent)]/20 transition-all duration-200";
  const glassStyle =
    "bg-[rgba(255,255,255,0.06)] backdrop-blur-md border-[rgba(255,255,255,0.1)] dark:bg-[rgba(255,255,255,0.04)] dark:border-[rgba(255,255,255,0.08)]";
  const hoverStyle =
    "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_25px_rgba(0,0,0,0.1)] active:scale-[0.98]";

  const cls = [
    base,
    variant === "default" ? defaultStyle : glassStyle,
    hover ? hoverStyle : "",
    extraClass ?? "",
  ].filter(Boolean).join(" ");

  const p = padding === "sm"
    ? { padding: "1rem" }
    : padding === "lg"
    ? { padding: "2rem" }
    : {};

  if (as === "a") {
    return (
      <a
        href={href}
        class={cls}
        style={{
          ...p,
          textDecoration: "none",
          color: "inherit",
          display: "block",
          ...style,
        }}
      >
        {children}
      </a>
    );
  }

  return <div class={cls} style={{ ...p, ...style }}>{children}</div>;
}
