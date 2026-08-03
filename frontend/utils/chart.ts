import { useEffect, useRef } from "preact/hooks";
import {
  Chart,
  type ChartConfiguration,
  type ChartType,
  type DefaultDataPoint,
  registerables,
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
  "total_executions",
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

export function useChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  function createChart<
    TType extends ChartType = ChartType,
    TData extends DefaultDataPoint<TType> = DefaultDataPoint<TType>,
  >(
    config: ChartConfiguration<TType, TData>,
  ) {
    if (!canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;

    chartRef.current?.destroy();
    chartRef.current = new Chart(ctx, config) as Chart;
  }

  useEffect(() => {
    return () => chartRef.current?.destroy();
  }, []);

  return { canvasRef, chartRef, createChart };
}
