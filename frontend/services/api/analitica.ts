// services/api/analitica.ts
import { peticionJson } from "./nucleo.ts";
import type {
  DisposicionTrazasGrafico,
  EjecucionReciente,
  EstadoSemaforo,
  MetricasSemestre,
  RespuestaListaGraficos,
} from "./tipos.ts";

export function obtenerHistorial(
  limit = 10,
  modalidad?: string,
): Promise<MetricasSemestre[]> {
  return peticionJson<MetricasSemestre[]>("/analytics/history", {
    params: { limit, modalidad },
  });
}

export function obtenerSemaforo(
  semester?: string,
  modalidad?: string,
): Promise<EstadoSemaforo> {
  return peticionJson<EstadoSemaforo>("/analytics/semaphore", {
    params: { semester, modalidad },
  });
}

export function obtenerReciente(
  modalidad?: string,
): Promise<EjecucionReciente> {
  return peticionJson<EjecucionReciente>("/analytics/latest", {
    params: { modalidad },
  });
}

export function listarGraficos(
  executionId: number,
): Promise<RespuestaListaGraficos> {
  return peticionJson<RespuestaListaGraficos>(
    `/analytics/executions/${executionId}/charts`,
  );
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
  const data = await peticionJson<DisposicionTrazasGrafico>(
    `/analytics/executions/${executionId}/charts/${chartName}`,
    { params: { theme } },
  );
  if (CHART_CACHE.size >= CACHE_MAX) {
    const firstKey = CHART_CACHE.keys().next().value;
    if (firstKey) CHART_CACHE.delete(firstKey);
  }
  CHART_CACHE.set(key, data);
  return data;
}
