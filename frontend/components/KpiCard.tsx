// components/KpiCard.tsx
export default function KpiCard(
  { value, label }: { value: string | number; label: string },
) {
  return (
    <div class="p-5 rounded-[0.625rem] bg-[var(--bg-primary)] border border-[var(--border-secondary)] flex flex-col gap-2">
      <span class="text-2xl font-bold leading-tight text-[var(--text-primary)]">
        {value}
      </span>
      <span class="text-[0.6875rem] text-[var(--text-secondary)] uppercase tracking-[0.03em]">
        {label}
      </span>
    </div>
  );
}
