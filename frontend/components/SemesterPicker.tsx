// components/SemesterPicker.tsx
import { useSignal } from "@preact/signals";
import { isValidSemester, formatSemester } from "../utils/date.ts";
import YearNav from "./YearNav.tsx";

const MONTH_LABELS: Record<string, string> = { A: "Ene - Jun", B: "Jul - Dic" };

function semesterToYearPeriod(s: string): { year: number; period: "A" | "B" } | null {
  if (!isValidSemester(s)) return null;
  return { year: parseInt(s.slice(0, 4), 10), period: s.slice(4).toUpperCase() as "A" | "B" };
}

interface Props {
  value: string;
  onChange: (semester: string) => void;
  availableSemesters?: string[];
  minYear?: number;
  maxYear?: number;
}

export default function SemesterPicker({ value, onChange, availableSemesters, minYear = 2026, maxYear }: Props) {
  const current = new Date();
  const resolvedMax = maxYear ?? (current.getFullYear() + 10);
  const initial = semesterToYearPeriod(value);
  const year = useSignal(initial?.year ?? current.getFullYear());
  const period = useSignal<"A" | "B">(initial?.period ?? (current.getMonth() <= 5 ? "A" : "B"));
  const availableSet = new Set(availableSemesters ?? []);

  const select = (y: number, p: "A" | "B") => { year.value = y; period.value = p; onChange(`${y}${p}`); };

  return (
    <div class="inline-flex flex-col gap-2">
      <YearNav year={year.value} minYear={minYear} maxYear={resolvedMax}
        onPrev={() => year.value > minYear && select(year.value - 1, period.value)}
        onNext={() => year.value < resolvedMax && select(year.value + 1, period.value)} />
      <div class="flex gap-2">
        {(["A", "B"] as const).map((p) => {
          const selected = period.value === p;
          return (
            <button type="button" key={p} onClick={() => select(year.value, p)}
              disabled={availableSemesters !== undefined && !availableSet.has(`${year.value}${p}`)}
              class={`flex-1 px-3 py-1.5 rounded-lg border text-sm font-medium transition ${
                selected ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                : "bg-[var(--bg-primary)] text-[var(--text-secondary)] border-[var(--border-secondary)] hover:bg-[var(--bg-tertiary)]"
              } disabled:opacity-30 disabled:cursor-not-allowed`}>
              <div class="leading-tight">{p}</div>
              <div class="text-[10px] opacity-80 leading-tight">{MONTH_LABELS[p]}</div>
            </button>
          );
        })}
      </div>
      <p class="text-sm text-[var(--text-secondary)] text-center select-none">Semestre {formatSemester(`${year.value}${period.value}`)}</p>
    </div>
  );
}
