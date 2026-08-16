// services/api/analytics.ts
import { authHeaders, BASE_URL, handleResponse } from "./core.ts";
import type {
  ChartsListResponse,
  ChartTracesLayout,
  LatestExecution,
  SemaphoreStatus,
  SemesterMetrics,
} from "./types.ts";

export async function getHistory(
  limit = 10,
  modalidad?: string,
): Promise<SemesterMetrics[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (modalidad) params.set("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/analytics/history?${params}`, {
    headers: { ...authHeaders() },
  });
  return handleResponse<SemesterMetrics[]>(response);
}

export async function getSemaphore(
  semester?: string,
  modalidad?: string,
): Promise<SemaphoreStatus> {
  const params = new URLSearchParams();
  if (semester) params.set("semester", semester);
  if (modalidad) params.set("modalidad", modalidad);
  const url = `${BASE_URL}/analytics/semaphore${
    params.toString() ? "?" + params.toString() : ""
  }`;
  const response = await fetch(url, { headers: { ...authHeaders() } });
  return handleResponse<SemaphoreStatus>(response);
}

export async function getLatest(modalidad?: string): Promise<LatestExecution> {
  const url = modalidad
    ? `${BASE_URL}/analytics/latest?modalidad=${modalidad}`
    : `${BASE_URL}/analytics/latest`;
  const response = await fetch(url, { headers: { ...authHeaders() } });
  return handleResponse<LatestExecution>(response);
}

export async function listCharts(
  executionId: number,
): Promise<ChartsListResponse> {
  const response = await fetch(
    `${BASE_URL}/analytics/executions/${executionId}/charts`,
    { headers: { ...authHeaders() } },
  );
  return handleResponse<ChartsListResponse>(response);
}

const CHART_CACHE = new Map<string, ChartTracesLayout>();
const CACHE_MAX = 20;

export async function getChartData(
  executionId: number,
  chartName: string,
  theme?: string,
  force = false,
): Promise<ChartTracesLayout> {
  const key = `${executionId}/${chartName}`;
  if (!force && CHART_CACHE.has(key)) return CHART_CACHE.get(key)!;
  const url = theme
    ? `${BASE_URL}/analytics/executions/${executionId}/charts/${chartName}?theme=${theme}`
    : `${BASE_URL}/analytics/executions/${executionId}/charts/${chartName}`;
  const response = await fetch(url, { headers: { ...authHeaders() } });
  const data = await handleResponse<ChartTracesLayout>(response);
  if (CHART_CACHE.size >= CACHE_MAX) {
    const firstKey = CHART_CACHE.keys().next().value;
    if (firstKey) CHART_CACHE.delete(firstKey);
  }
  CHART_CACHE.set(key, data);
  return data;
}
