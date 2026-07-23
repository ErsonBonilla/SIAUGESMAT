import { useEffect } from "preact/hooks";
import { useComputed } from "@preact/signals";
import type { SemesterMetrics } from "../services/api.ts";
import { useChart, METRIC_LABELS, METRIC_COLORS, createGradient } from "../utils/chart.ts";
import { darkSignal } from "../utils/theme.ts";

interface MetricsChartProps {
  data: SemesterMetrics[];
  metrics?: Array<keyof Omit<SemesterMetrics, "semester">>;
  selectedSemesters?: string[];
}

const STACK_ORDER: Record<string, number> = {
  total_errors: 0,
  total_enrollments: 1,
  total_users_created: 2,
  total_courses_created: 3,
  avg_duration_seconds: 4,
};

function gradientPlugin(ctx: CanvasRenderingContext2D, height: number, dark: boolean) {
  return {
    id: "gradientFill",
    beforeDraw(chart: { data: { datasets: { backgroundColor: unknown; label?: string }[] }; chartArea: { top: number } }) {

      for (const ds of chart.data.datasets) {
        const label = ds.label || "";
        const entry = Object.entries(METRIC_LABELS).find(([, v]) => v === label);
        const key = entry?.[0];
        const color = key ? METRIC_COLORS[key] : METRIC_COLORS.total_errors;
        if (color) {
          ds.backgroundColor = createGradient(ctx, color, dark, height);
        }
      }
    },
  };
}

export default function MetricsChart(
  { data, metrics, selectedSemesters }: MetricsChartProps,
) {
  const dark = useComputed(() => darkSignal.value);
  const { canvasRef, createChart } = useChart(dark.value);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const filtered = !selectedSemesters?.length
      ? data
      : data.filter((d) => selectedSemesters.includes(d.semester));
    if (filtered.length === 0) return;

    const selectedMetrics = metrics || [
      "total_courses_created",
      "total_users_created",
      "total_enrollments",
      "total_errors",
    ];

    const sorted = [...selectedMetrics].sort(
      (a, b) => (STACK_ORDER[a] ?? 99) - (STACK_ORDER[b] ?? 99),
    );

    const labels = filtered.map((d) => d.semester).reverse();
    const datasets = sorted.map((metric) => ({
      label: METRIC_LABELS[metric] || metric,
      data: filtered.map((d) => (d[metric] as number) || 0).reverse(),
      backgroundColor: "rgba(0,0,0,0.1)",
      borderColor: METRIC_COLORS[metric]?.base || "#999",
      borderWidth: 0.5,
      borderRadius: { topLeft: 4, topRight: 4 },
      borderSkipped: false,
      hoverBackgroundColor: METRIC_COLORS[metric]?.light || "#ccc",
      hoverBorderWidth: 1.5,
      barPercentage: 0.65,
      categoryPercentage: 0.8,
    }));

    const height = canvasRef.current?.offsetHeight || 400;
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    const plugin = gradientPlugin(ctx, height, dark.value);

    createChart({
      type: "bar",
      data: { labels, datasets },
      options: {
        scales: {
          x: { stacked: true },
          y: { stacked: true },
        },
      },
      plugins: [plugin],
    } as never);
  }, [data, metrics, selectedSemesters, dark.value]);

  const noSelection = selectedSemesters !== undefined && selectedSemesters.length === 0;

  if (noSelection) {
    return (
      <div class="text-center text-[var(--text-secondary)] py-12">
        <p class="text-lg font-medium">Sin datos históricos</p>
        <p class="text-sm mt-2">
          Una vez se ejecuten procesos ETL, las métricas aparecerán aquí.
        </p>
      </div>
    );
  }

  if (data.length > 0 && noSelection) {
    return (
      <div class="text-center text-[var(--text-secondary)] py-12">
        <p class="text-lg font-medium">Selecciona uno o más semestres</p>
        <p class="text-sm mt-2">
          Usa el selector superior para elegir los semestres a visualizar.
        </p>
      </div>
    );
  }

  return (
    <div class="w-full chart-container">
      <canvas ref={canvasRef} />
    </div>
  );
}
