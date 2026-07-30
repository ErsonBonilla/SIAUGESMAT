import { useSignal } from "@preact/signals";
import { formatSemester, isValidSemester } from "../utils/date.ts";
import YearNav from "./YearNav.tsx";
import PeriodButton from "./PeriodButton.tsx";

function semesterToYearPeriod(
  s: string,
): { year: number; period: "A" | "B" } | null {
  if (!isValidSemester(s)) return null;
  return {
    year: parseInt(s.slice(0, 4), 10),
    period: s.slice(4).toUpperCase() as "A" | "B",
  };
}

interface Props {
  value: string;
  onChange: (semester: string) => void;
  availableSemesters?: string[];
  minYear?: number;
  maxYear?: number;
}

export default function SemesterPicker(
  { value, onChange, availableSemesters, minYear = 2026, maxYear }: Props,
) {
  const current = new Date();
  const resolvedMax = maxYear ?? (current.getFullYear() + 10);
  const initial = semesterToYearPeriod(value);
  const year = useSignal(initial?.year ?? current.getFullYear());
  const period = useSignal<"A" | "B">(
    initial?.period ?? (current.getMonth() <= 5 ? "A" : "B"),
  );
  const availableSet = new Set(availableSemesters ?? []);

  const select = (y: number, p: "A" | "B") => {
    year.value = y;
    period.value = p;
    onChange(`${y}${p}`);
  };

  return (
    <div class="inline-flex flex-col gap-2">
      <YearNav
        year={year.value}
        minYear={minYear}
        maxYear={resolvedMax}
        onPrev={() =>
          year.value > minYear && select(year.value - 1, period.value)}
        onNext={() =>
          year.value < resolvedMax && select(year.value + 1, period.value)}
      />
      <div class="flex gap-2">
        {(["A", "B"] as const).map((p) => (
          <PeriodButton
            key={p}
            period={p}
            selected={period.value === p}
            disabled={availableSemesters !== undefined &&
              !availableSet.has(`${year.value}${p}`)}
            onClick={() => select(year.value, p)}
          />
        ))}
      </div>
      <p class="text-sm text-[var(--text-secondary)] text-center select-none">
        Semestre {formatSemester(`${year.value}${period.value}`)}
      </p>
    </div>
  );
}
