// islands/Chart.tsx
import { useEffect, useRef } from "preact/hooks";
import { getChartData } from "../services/api.ts";
import { loadPlotly } from "../utils/plotly.ts";

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
  const containerRef = useRef<HTMLDivElement>(null);
  const chartId = `chart-${chartName}-${executionId}`;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;

    (async () => {
      try {
        await loadPlotly();
        if (cancelled) return;

        const data = await getChartData(executionId, chartName);
        if (cancelled) return;

        const layout = {
          ...data.layout,
          width: undefined,
          height: undefined,
          autosize: true,
        };

        window.Plotly.newPlot(container, data.traces, layout, {
          responsive: true,
          displayModeBar: true,
          modeBarButtonsToRemove: ["sendDataToCloud"],
        });
      } catch (err) {
        if (!cancelled) {
          container.innerHTML =
            `<div class="text-red-500 text-center p-4">Error al cargar gráfico: ${
              err instanceof Error ? err.message : "Error desconocido"
            }</div>`;
        }
      }
    })();

    return () => {
      cancelled = true;
      if (container) {
        try {
          window.Plotly?.purge(container);
        } catch {
          // ignore
        }
      }
    };
  }, [executionId, chartName]);

  return (
    <div class="bg-[var(--bg-primary)] rounded-lg shadow p-4">
      {title && (
        <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-3">
          {title}
        </h3>
      )}
      <div
        id={chartId}
        ref={containerRef}
        style={{
          width: width || "100%",
          height: height || "400px",
        }}
      />
    </div>
  );
}
