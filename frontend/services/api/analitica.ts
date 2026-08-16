// services/api/analytics.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type {
  DisposicionTrazasGrafico,
  EjecucionReciente,
  EstadoSemaforo,
  MetricasSemestre,
  RespuestaListaGraficos,
} from "./tipos.ts";

export async function obtenerHistorial(
  limit = 10,
  modalidad?: string,
): Promise<MetricasSemestre[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (modalidad) params.set("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/analytics/history?${params}`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<MetricasSemestre[]>(response);
}

export async function obtenerSemaforo(
  semester?: string,
  modalidad?: string,
): Promise<EstadoSemaforo> {
  const params = new URLSearchParams();
  if (semester) params.set("semester", semester);
  if (modalidad) params.set("modalidad", modalidad);
  const url = `${BASE_URL}/analytics/semaphore${
    params.toString() ? "?" + params.toString() : ""
  }`;
  const response = await fetch(url, { headers: { ...cabecerasAuth() } });
  return manejarRespuesta<EstadoSemaforo>(response);
}

export async function obtenerReciente(
  modalidad?: string,
): Promise<EjecucionReciente> {
  const url = modalidad
    ? `${BASE_URL}/analytics/latest?modalidad=${modalidad}`
    : `${BASE_URL}/analytics/latest`;
  const response = await fetch(url, { headers: { ...cabecerasAuth() } });
  return manejarRespuesta<EjecucionReciente>(response);
}

export async function listarGraficos(
  executionId: number,
): Promise<RespuestaListaGraficos> {
  const response = await fetch(
    `${BASE_URL}/analytics/executions/${executionId}/charts`,
    { headers: { ...cabecerasAuth() } },
  );
  return manejarRespuesta<RespuestaListaGraficos>(response);
}

const CHART_CACHE = new Map<string, DisposicionTrazasGrafico>();
const CACHE_MAX = 20;

export async function obtenerDatosGrafico(
  executionId: number,
  chartName: string,
  theme?: string,
  force = false,
): Promise<DisposicionTrazasGrafico> {
  const key = `${executionId}/${chartName}/${theme ?? "default"}`;
  if (!force && CHART_CACHE.has(key)) return CHART_CACHE.get(key)!;
  const url = theme
    ? `${BASE_URL}/analytics/executions/${executionId}/charts/${chartName}?theme=${theme}`
    : `${BASE_URL}/analytics/executions/${executionId}/charts/${chartName}`;
  const response = await fetch(url, { headers: { ...cabecerasAuth() } });
  const data = await manejarRespuesta<DisposicionTrazasGrafico>(response);
  if (CHART_CACHE.size >= CACHE_MAX) {
    const firstKey = CHART_CACHE.keys().next().value;
    if (firstKey) CHART_CACHE.delete(firstKey);
  }
  CHART_CACHE.set(key, data);
  return data;
}
