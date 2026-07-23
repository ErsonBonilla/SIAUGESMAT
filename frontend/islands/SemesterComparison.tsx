// islands/SemesterComparison.tsx
import { useSignal, useComputed } from "@preact/signals";
import { useEffect } from "preact/hooks";
import type { SemesterMetrics } from "../services/api.ts";
import { useChart, METRIC_LABELS, METRIC_KEYS } from "../utils/chart.ts";
import SemesterPicker from "../components/SemesterPicker.tsx";

interface SemesterComparisonProps {
  allMetrics: SemesterMetrics[];
}

const COLOR_A = "#ED3237";
const COLOR_B = "#1E40AF";

export default function SemesterComparison({ allMetrics }: SemesterComparisonProps) {
  const semesterA = useSignal<string>("");
  const semesterB = useSignal<string>("");
  const { canvasRef, createChart } = useChart();

  const availableSemesters = useComputed(() => {
    return allMetrics.map((m) => m.semester).sort();
  });

  const metricsA = useComputed(() =>
    allMetrics.find((m) => m.semester === semesterA.value)
  );
  const metricsB = useComputed(() =>
    allMetrics.find((m) => m.semester === semesterB.value)
  );

  const bothSelected = useComputed(
    () => semesterA.value && semesterB.value && semesterA.value !== semesterB.value
  );

  const handleSwap = () => {
    const temp = semesterA.value;
    semesterA.value = semesterB.value;
    semesterB.value = temp;
  };

  useEffect(() => {
    if (!metricsA.value || !metricsB.value) return;

    const labels = METRIC_KEYS.map((key) => METRIC_LABELS[key]);
    const dataA = METRIC_KEYS.map((key) => metricsA.value![key] as number || 0);
    const dataB = METRIC_KEYS.map((key) => metricsB.value![key] as number || 0);

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
          <SemesterPicker
            value={semesterA.value}
            onChange={(s) => (semesterA.value = s)}
            availableSemesters={availableSemesters.value.filter((s) => s !== semesterB.value)}
          />
        </div>

        {semesterA.value && semesterB.value && (
          <button
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
          <SemesterPicker
            value={semesterB.value}
            onChange={(s) => (semesterB.value = s)}
            availableSemesters={availableSemesters.value.filter((s) => s !== semesterA.value)}
          />
        </div>
      </div>

      {!bothSelected.value && (
        <div class="text-center text-[var(--text-secondary)] py-12">
          <p class="text-lg font-medium">Seleccione dos semestres para comparar</p>
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
