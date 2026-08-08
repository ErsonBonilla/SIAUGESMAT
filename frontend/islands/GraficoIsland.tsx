// islands/GraficoIsland.tsx
import { useEffect } from "preact/hooks";
import { getChartData } from "../services/api.ts";
import { darkSignal } from "../utils/theme.ts";
import { useChart } from "../utils/chart.ts";
import { plotlyToChartConfig } from "../utils/plotlyToChart.ts";

interface ChartProps {
  executionId: number;
  chartName: string;
  title?: string;
  width?: string;
  height?: string;
}

export default function Chart(
  { executionId, chartName, title, width, height }: ChartProps,
) {
  const { canvasRef, createChart } = useChart();
  const chartId = `chart-${chartName}-${executionId}`;

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const theme = darkSignal.value ? "dark" : "light";
        const data = await getChartData(executionId, chartName, theme);
        if (cancelled) return;
        createChart(plotlyToChartConfig(data));
      } catch (err) {
        if (!cancelled) {
          console.error("Error al cargar gráfico:", err);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [executionId, chartName, darkSignal.value]);

  return (
    <div class="bg-[var(--bg-primary)] rounded-lg shadow p-4">
      {title && (
        <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-3">
          {title}
        </h3>
      )}
      <div
        id={chartId}
        style={{
          width: width || "100%",
          height: height || "400px",
          position: "relative",
        }}
      >
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />
      </div>
    </div>
  );
}
