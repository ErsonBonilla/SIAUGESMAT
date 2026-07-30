import { useSignal } from "@preact/signals";
import { formatSemester } from "../utils/date.ts";
import YearNav from "./YearNav.tsx";
import PeriodButton from "./PeriodButton.tsx";

interface Props {
  selected: string[];
  onChange: (semesters: string[]) => void;
  availableSemesters?: string[];
  minYear?: number;
  maxYear?: number;
}

export default function SemesterMultiPicker(
  { selected, onChange, availableSemesters, minYear = 2026, maxYear }: Props,
) {
  const current = new Date();
  const resolvedMax = maxYear ?? (current.getFullYear() + 10);
  const year = useSignal(current.getFullYear());
  const availableSet = new Set(availableSemesters ?? []);
  const selectedSet = new Set(selected);

  const toggle = (y: number, p: string) => {
    const s = `${y}${p}`;
    onChange(
      selectedSet.has(s)
        ? selected.filter((x) => x !== s)
        : [...selected, s].sort(),
    );
  };

  return (
    <div class="inline-flex flex-col gap-2">
      <YearNav
        year={year.value}
        minYear={minYear}
        maxYear={resolvedMax}
        onPrev={() => year.value > minYear && (year.value -= 1)}
        onNext={() => year.value < resolvedMax && (year.value += 1)}
      />
      <div class="flex gap-2">
        {(["A", "B"] as const).map((p) => {
          const s = `${year.value}${p}`;
          return (
            <PeriodButton
              key={p}
              period={p}
              selected={selectedSet.has(s)}
              disabled={availableSemesters !== undefined &&
                !availableSet.has(s)}
              onClick={() => toggle(year.value, p)}
            />
          );
        })}
      </div>
      {selected.length > 0 && (
        <div class="flex flex-wrap items-center gap-1.5 mt-1">
          {selected.map((s) => (
            <span
              key={s}
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--brand-red-50)] text-[var(--brand-red)] text-xs font-medium border border-[var(--brand-red-200)]"
            >
              {formatSemester(s)}
              <button
                type="button"
                onClick={() => onChange(selected.filter((x) => x !== s))}
                class="hover:text-red-700 transition leading-none"
                aria-label={`Quitar ${formatSemester(s)}`}
              >
                ✕
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={() => onChange([])}
            class="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] underline ml-1"
          >
            Limpiar
          </button>
        </div>
      )}
    </div>
  );
}
