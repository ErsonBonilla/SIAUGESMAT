import { useEffect, useRef } from "preact/hooks";
import {
  Chart,
  registerables,
  type ChartConfiguration,
  type ChartType,
  type DefaultDataPoint,
} from "chart.js";

Chart.register(...registerables);

export const METRIC_LABELS: Record<string, string> = {
  total_executions: "Ejecuciones",
  total_courses_created: "Cursos creados",
  total_users_created: "Usuarios creados",
  total_enrollments: "Matrículas",
  total_errors: "Errores",
  avg_duration_seconds: "Duración media (s)",
};

type ColorPair = { base: string; light: string };
export const METRIC_COLORS: Record<string, ColorPair> = {
  total_executions: { base: "#1E40AF", light: "#93C5FD" },
  total_courses_created: { base: "#00A859", light: "#79d1a8" },
  total_users_created: { base: "#4B5563", light: "#9CA3AF" },
  total_enrollments: { base: "#D97706", light: "#FDE68A" },
  total_errors: { base: "#ED3237", light: "#fcecec" },
  avg_duration_seconds: { base: "#6B7280", light: "#D1D5DB" },
};

export const METRIC_KEYS = [
  "total_courses_created",
  "total_users_created",
  "total_enrollments",
  "total_errors",
  "avg_duration_seconds",
] as const;

export function createGradient(
  ctx: CanvasRenderingContext2D,
  color: ColorPair,
  dark: boolean,
  height: number,
): CanvasGradient {
  const top = dark ? color.light : color.base;
  const bottom = dark ? color.base : color.light;
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, top);
  gradient.addColorStop(1, bottom);
  return gradient;
}

export function useChart(dark = false) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  function createChart<
    TType extends ChartType = ChartType,
    TData extends DefaultDataPoint<TType> = DefaultDataPoint<TType>,
  >(
    config: ChartConfiguration<TType, TData>,
  ) {
    if (!canvasRef.current) return;
    chartRef.current?.destroy();
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;

    const gridColor = dark
      ? "rgba(255, 255, 255, 0.08)"
      : "rgba(0, 0, 0, 0.07)";
    const tickColor = dark
      ? "rgba(255, 255, 255, 0.6)"
      : "rgba(0, 0, 0, 0.5)";
    const titleColor = dark
      ? "rgba(255, 255, 255, 0.8)"
      : "rgba(0, 0, 0, 0.7)";

    const defaults = {
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 800,
          easing: "easeOutQuart" as const,
        },
        plugins: {
          legend: {
            position: "bottom" as const,
            labels: {
              usePointStyle: true,
              pointStyle: "circle",
              padding: 16,
              font: { size: 12, weight: "500" as const },
              color: tickColor,
            },
          },
          tooltip: {
            cornerRadius: 8,
            padding: 12,
            titleFont: { weight: "600" as const, size: 13 },
            bodyFont: { size: 12 },
            backgroundColor: dark
              ? "rgba(30, 30, 30, 0.95)"
              : "rgba(255, 255, 255, 0.95)",
            titleColor: dark ? "#fff" : "#111",
            bodyColor: dark ? "#ccc" : "#333",
            borderColor: dark
              ? "rgba(255, 255, 255, 0.1)"
              : "rgba(0, 0, 0, 0.1)",
            borderWidth: 1,
            boxPadding: 4,
            callbacks: {
              label: (context: {
                dataset: { label?: string };
                parsed: { y: number };
                dataIndex: number;
                chart: { data: { datasets: { data: number[] }[] } };
              }) => {
                const label = context.dataset.label || "";
                const value = context.parsed.y;
                let total = 0;
                for (const ds of context.chart.data.datasets) {
                  total += ds.data[context.dataIndex] as number;
                }
                return `${label}: ${value}`;
              },
              afterBody: (contexts: { chart: { data: { datasets: { data: number[] }[] } }; dataIndex: number }[]) => {
                if (!contexts.length) return;
                const idx = contexts[0].dataIndex;
                let total = 0;
                for (const ds of contexts[0].chart.data.datasets) {
                  total += ds.data[idx] as number;
                }
                return `Total: ${total}`;
              },
            },
          },
        },
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            ticks: { color: tickColor, font: { size: 11 } },
            title: {
              display: true,
              text: "Semestre",
              color: titleColor,
              font: { size: 12, weight: "500" as const },
            },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              stepSize: 1,
              color: tickColor,
              font: { size: 11 },
            },
            title: {
              display: true,
              text: "Cantidad",
              color: titleColor,
              font: { size: 12, weight: "500" as const },
            },
            grid: {
              color: gridColor,
              drawBorder: false,
              borderDash: [3, 3] as [number, number],
            },
          },
        },
      },
    };

    chartRef.current?.destroy();
    chartRef.current = new Chart(ctx, config) as unknown as Chart;
  }

  useEffect(() => {
    return () => chartRef.current?.destroy();
  }, []);

  return { canvasRef, chartRef, createChart };
}
