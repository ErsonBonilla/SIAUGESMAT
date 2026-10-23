// utils/plotly-a-grafico.ts
// Adaptador que convierte el JSON Plotly ({traces, layout}) que sirve el backend
// en una configuración de Chart.js. Soporta los 5 gráficos de reportes:
// barras (horizontal/vertical) y donuts (pie con hole).
import type { ChartConfiguration, ChartType } from "chart.js";

interface TrazaPlotly {
  type?: string;
  orientation?: string;
  x?: unknown[];
  y?: unknown[];
  labels?: unknown[];
  values?: unknown[];
  text?: unknown[];
  marker?: {
    color?: string | string[];
    colors?: string[];
  };
  name?: string;
  hole?: number;
}

interface DisposicionPlotly {
  title?: { text?: string };
  paper_bgcolor?: string;
  plot_bgcolor?: string;
  font?: { color?: string };
  showlegend?: boolean;
  legend?: { orientation?: string };
  xaxis?: { title?: { text?: string } | string; tickangle?: number };
  yaxis?: { title?: { text?: string } | string };
  barmode?: string;
}

export interface DatosGraficoPlotly {
  traces: unknown[];
  layout: DisposicionPlotly;
}

function titleText(t: unknown): string {
  if (typeof t === "string") return t;
  if (t && typeof t === "object") {
    const v = (t as { text?: unknown }).text;
    return typeof v === "string" ? v : "";
  }
  return "";
}

export function configGraficoDesdePlotly(
  data: DatosGraficoPlotly,
): ChartConfiguration {
  const traces = (data.traces ?? []) as TrazaPlotly[];
  const layout = data.layout ?? {};
  const textColor = layout.font?.color ?? "#374151";
  const gridColor = layout.plot_bgcolor === "#1e1e2e" ? "#45475a" : "#E0E0E0";

  if (traces.length === 0) {
    return {
      type: "bar" as ChartType,
      data: { labels: [], datasets: [] },
      options: {},
    };
  }

  const first = traces[0];

  if (first.type === "pie") {
    const labels = (first.labels ?? []) as string[];
    const values = (first.values ?? []) as number[];
    const colors = first.marker?.colors ?? [];
    return {
      type: "doughnut" as ChartType,
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: layout.paper_bgcolor ?? "#FFFFFF",
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: layout.showlegend !== false,
            position: layout.legend?.orientation === "h" ? "bottom" : "right",
            labels: { color: textColor },
          },
        },
      },
    };
  }

  // Barras (orientación h = indexAxis y)
  const horizontal = first.orientation === "h";
  const labels = (horizontal ? first.y : first.x ?? []) as string[];
  const values = (horizontal ? first.x : first.y ?? []) as number[];
  const rawColor = first.marker?.color;
  const barColor = Array.isArray(rawColor)
    ? rawColor[0]
    : rawColor ?? "#00A859";

  return {
    type: "bar" as ChartType,
    data: {
      labels,
      datasets: [{
        label: first.name ?? "",
        data: values,
        backgroundColor: barColor,
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: horizontal ? ("y" as const) : ("x" as const),
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor },
          title: {
            display: true,
            text: titleText(layout.xaxis?.title),
            color: textColor,
          },
        },
        y: {
          grid: { color: gridColor },
          ticks: { color: textColor },
          title: {
            display: true,
            text: titleText(layout.yaxis?.title),
            color: textColor,
          },
        },
      },
    },
  };
}
