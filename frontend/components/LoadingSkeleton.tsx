// components/LoadingSkeleton.tsx

type Variant = "table" | "chart" | "kpi";

interface Props {
  variant?: Variant;
  rows?: number;
}

export default function LoadingSkeleton(
  { variant = "table", rows = 5 }: Props,
) {
  if (variant === "chart") {
    return (
      <div class="flex flex-col gap-4 animate-pulse">
        <div class="h-6 w-48 bg-[var(--bg-skeleton)] rounded-lg" />
        <div class="h-64 bg-[var(--bg-tertiary)] rounded-xl" />
      </div>
    );
  }

  if (variant === "kpi") {
    return (
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6 animate-pulse">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} class="h-24 bg-[var(--bg-skeleton)] rounded" />
        ))}
      </div>
    );
  }

  return (
    <div class="animate-pulse space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} class="h-12 bg-[var(--bg-skeleton)] rounded" />
      ))}
    </div>
  );
}
