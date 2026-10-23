import { useSignal } from "@preact/signals";
import { formatearSemestre } from "../utils/fechas.ts";
import NavegacionAnios from "./NavegacionAnios.tsx";
import BotonPeriodo from "./BotonPeriodo.tsx";

interface Props {
  selected: string[];
  onChange: (semesters: string[]) => void;
  semestresDisponibles?: string[];
  anioMinimo?: number;
  anioMaximo?: number;
}

export default function SelectorMultiplesSemestres(
  { selected, onChange, semestresDisponibles, anioMinimo = 2026, anioMaximo }:
    Props,
) {
  const current = new Date();
  const resolvedMax = anioMaximo ?? (current.getFullYear() + 10);
  const year = useSignal(current.getFullYear());
  const availableSet = new Set(semestresDisponibles ?? []);
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
      <NavegacionAnios
        year={year.value}
        anioMinimo={anioMinimo}
        anioMaximo={resolvedMax}
        alAnterior={() => year.value > anioMinimo && (year.value -= 1)}
        alSiguiente={() => year.value < resolvedMax && (year.value += 1)}
      />
      <div class="flex gap-2">
        {(["A", "B"] as const).map((p) => {
          const s = `${year.value}${p}`;
          return (
            <BotonPeriodo
              key={p}
              period={p}
              selected={selectedSet.has(s)}
              disabled={semestresDisponibles !== undefined &&
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
              {formatearSemestre(s)}
              <button
                type="button"
                onClick={() => onChange(selected.filter((x) => x !== s))}
                class="hover:text-red-700 transition leading-none"
                aria-label={`Quitar ${formatearSemestre(s)}`}
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
