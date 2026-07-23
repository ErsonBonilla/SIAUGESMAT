export default function YearNav({ year, minYear, maxYear, onPrev, onNext, shadow, scale }: {
  year: number; minYear: number; maxYear: number;
  onPrev: () => void; onNext: () => void; shadow?: boolean; scale?: boolean;
}) {
  const btn = "w-8 h-8 flex items-center justify-center rounded-lg border border-[var(--border-secondary)] bg-[var(--bg-primary)] text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition disabled:opacity-30 disabled:cursor-not-allowed" +
    (shadow ? " hover:shadow-sm" : "") +
    (scale ? " active:scale-95 transition-all duration-150 disabled:active:scale-100" : "");
  return (
    <div class="flex items-center gap-3">
      <button type="button" onClick={onPrev} disabled={year <= minYear} class={btn} aria-label="Año anterior">◀</button>
      <span class="text-lg font-semibold text-[var(--text-primary)] min-w-[72px] text-center select-none">{year}</span>
      <button type="button" onClick={onNext} disabled={year >= maxYear} class={btn} aria-label="Año siguiente">▶</button>
    </div>
  );
}
