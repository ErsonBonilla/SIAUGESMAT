import { useSignal } from "@preact/signals";
import { esSemestreValido, formatearSemestre } from "../utils/fechas.ts";
import NavegacionAnios from "./NavegacionAnios.tsx";
import BotonPeriodo from "./BotonPeriodo.tsx";

function semesterToYearPeriod(
  s: string,
): { year: number; period: "A" | "B" } | null {
  if (!esSemestreValido(s)) return null;
  return {
    year: parseInt(s.slice(0, 4), 10),
    period: s.slice(4).toUpperCase() as "A" | "B",
  };
}

interface Props {
  value: string;
  onChange: (semester: string) => void;
  semestresDisponibles?: string[];
  anioMinimo?: number;
  anioMaximo?: number;
}

export default function SelectorSemestre(
  { value, onChange, semestresDisponibles, anioMinimo = 2026, anioMaximo }:
    Props,
) {
  const current = new Date();
  const resolvedMax = anioMaximo ?? (current.getFullYear() + 10);
  const initial = semesterToYearPeriod(value);
  const year = useSignal(initial?.year ?? current.getFullYear());
  const period = useSignal<"A" | "B">(
    initial?.period ?? (current.getMonth() <= 5 ? "A" : "B"),
  );
  const availableSet = new Set(semestresDisponibles ?? []);

  const select = (y: number, p: "A" | "B") => {
    year.value = y;
    period.value = p;
    onChange(`${y}${p}`);
  };

  return (
    <div class="inline-flex flex-col gap-2">
      <NavegacionAnios
        year={year.value}
        anioMinimo={anioMinimo}
        anioMaximo={resolvedMax}
        alAnterior={() =>
          year.value > anioMinimo && select(year.value - 1, period.value)}
        alSiguiente={() =>
          year.value < resolvedMax && select(year.value + 1, period.value)}
      />
      <div class="flex gap-2">
        {(["A", "B"] as const).map((p) => (
          <BotonPeriodo
            key={p}
            period={p}
            selected={period.value === p}
            disabled={semestresDisponibles !== undefined &&
              !availableSet.has(`${year.value}${p}`)}
            onClick={() => select(year.value, p)}
          />
        ))}
      </div>
      <p class="text-sm text-[var(--text-secondary)] text-center select-none">
        Semestre {formatearSemestre(`${year.value}${period.value}`)}
      </p>
    </div>
  );
}
