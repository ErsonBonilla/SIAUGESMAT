// islands/ComparacionSemestre.tsx
import { useComputed, useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import type { MetricasSemestre } from "../services/api.ts";
import {
  CLAVES_METRICAS,
  ETIQUETAS_METRICAS,
  useChart,
} from "../utils/grafico.ts";
import SelectorSemestre from "../components/SelectorSemestre.tsx";

interface PropsComparacionSemestre {
  allMetrics: MetricasSemestre[];
}

const COLOR_A = "#ED3237";
const COLOR_B = "#1E40AF";

export default function ComparacionSemestre(
  { allMetrics }: PropsComparacionSemestre,
) {
  const semesterA = useSignal<string>("");
  const semesterB = useSignal<string>("");
  const { canvasRef, createChart } = useChart();

  const semestresDisponibles = useComputed(() => {
    return allMetrics.map((m) => m.semester).sort();
  });

  const metricsA = useComputed(() =>
    allMetrics.find((m) => m.semester === semesterA.value)
  );
  const metricsB = useComputed(() =>
    allMetrics.find((m) => m.semester === semesterB.value)
  );

  const bothSelected = useComputed(
    () =>
      semesterA.value && semesterB.value && semesterA.value !== semesterB.value,
  );

  const handleSwap = () => {
    const temp = semesterA.value;
    semesterA.value = semesterB.value;
    semesterB.value = temp;
  };

  useEffect(() => {
    if (!metricsA.value || !metricsB.value) return;

    const labels = CLAVES_METRICAS.map((key) => ETIQUETAS_METRICAS[key]);
    const dataA = CLAVES_METRICAS.map((key) =>
      metricsA.value![key] as number || 0
    );
    const dataB = CLAVES_METRICAS.map((key) =>
      metricsB.value![key] as number || 0
    );

    createChart({
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: `Semestre ${semesterA.value}`,
            data: dataA,
            backgroundColor: COLOR_A,
            borderColor: COLOR_A,
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: `Semestre ${semesterB.value}`,
            data: dataB,
            backgroundColor: COLOR_B,
            borderColor: COLOR_B,
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
    });
  }, [metricsA.value, metricsB.value, semesterA.value, semesterB.value]);

  return (
    <div>
      <div class="flex flex-wrap gap-6 mb-6 items-end">
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1">
            Semestre A
          </label>
          <SelectorSemestre
            value={semesterA.value}
            onChange={(s) => (semesterA.value = s)}
            semestresDisponibles={semestresDisponibles.value.filter((s) =>
              s !== semesterB.value
            )}
          />
        </div>

        {semesterA.value && semesterB.value && (
          <button
            type="button"
            onClick={handleSwap}
            class="px-3 py-2 border border-[var(--border-secondary)] rounded-lg bg-[var(--bg-primary)] hover:bg-[var(--bg-tertiary)] transition text-sm text-[var(--text-secondary)] mt-6"
            title="Intercambiar semestres"
          >
            ⇆
          </button>
        )}

        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1">
            Semestre B
          </label>
          <SelectorSemestre
            value={semesterB.value}
            onChange={(s) => (semesterB.value = s)}
            semestresDisponibles={semestresDisponibles.value.filter((s) =>
              s !== semesterA.value
            )}
          />
        </div>
      </div>

      {!bothSelected.value && (
        <div class="text-center text-[var(--text-secondary)] py-12">
          <p class="text-lg font-medium">
            Seleccione dos semestres para comparar
          </p>
        </div>
      )}

      {bothSelected.value && (
        <div class="w-full chart-container">
          <canvas ref={canvasRef} />
        </div>
      )}
    </div>
  );
}
