// components/SemesterMultiPicker.tsx
import { useSignal } from "@preact/signals";
import { formatSemester } from "../utils/date.ts";
import YearNav from "./YearNav.tsx";

const MONTH_LABELS: Record<string, string> = { A: "Ene - Jun", B: "Jul - Dic" };

interface Props {
  selected: string[];
  onChange: (semesters: string[]) => void;
  availableSemesters?: string[];
  minYear?: number;
  maxYear?: number;
}

export default function SemesterMultiPicker({ selected, onChange, availableSemesters, minYear = 2026, maxYear }: Props) {
  const current = new Date();
  const resolvedMax = maxYear ?? (current.getFullYear() + 10);
  const year = useSignal(current.getFullYear());
  const availableSet = new Set(availableSemesters ?? []);
  const selectedSet = new Set(selected);

  const toggle = (y: number, p: string) => {
    const s = `${y}${p}`;
    onChange(selectedSet.has(s) ? selected.filter((x) => x !== s) : [...selected, s].sort());
  };

  return (
    <div class="inline-flex flex-col gap-2">
      <YearNav year={year.value} minYear={minYear} maxYear={resolvedMax}
        onPrev={() => year.value > minYear && (year.value -= 1)}
        onNext={() => year.value < resolvedMax && (year.value += 1)}
        shadow scale />
      <div class="flex gap-2">
        {(["A", "B"] as const).map((p) => {
          const s = `${year.value}${p}`;
          const isSel = selectedSet.has(s);
          return (
            <button type="button" key={p} onClick={() => toggle(year.value, p)}
              disabled={availableSemesters !== undefined && !availableSet.has(s)}
              class={`flex-1 px-3 py-1.5 rounded-lg border text-sm font-medium transition-all duration-150 active:scale-95 ${
                isSel ? "bg-[var(--accent)] text-white border-[var(--accent)] shadow-sm"
                : "bg-[var(--bg-primary)] text-[var(--text-secondary)] border-[var(--border-secondary)] hover:bg-[var(--bg-tertiary)] hover:shadow-sm"
              } disabled:opacity-30 disabled:cursor-not-allowed disabled:active:scale-100`}>
              <div class="leading-tight">{p}</div>
              <div class="text-[10px] opacity-80 leading-tight">{MONTH_LABELS[p]}</div>
            </button>
          );
        })}
      </div>
      {selected.length > 0 && (
        <div class="flex flex-wrap items-center gap-1.5 mt-1">
          {selected.map((s) => (
            <span key={s} class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--brand-red-50)] text-[var(--brand-red)] text-xs font-medium border border-[var(--brand-red-200)] animate-scaleIn">
              {formatSemester(s)}
              <button type="button" onClick={() => onChange(selected.filter((x) => x !== s))}
                class="hover:text-red-700 transition leading-none" aria-label={`Quitar ${formatSemester(s)}`}>✕</button>
            </span>
          ))}
          <button type="button" onClick={() => onChange([])}
            class="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] underline ml-1 transition-all duration-150">Limpiar</button>
        </div>
      )}
    </div>
  );
}
