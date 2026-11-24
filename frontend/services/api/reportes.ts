// services/api/reportes.ts
import { BASE_URL, cabecerasAuth, peticionJson } from "./nucleo.ts";
import type { RespuestaListaReportes } from "./tipos.ts";

export function obtenerUrlDescargaReporte(executionId: number): string {
  return `${BASE_URL}/reports/${executionId}/reports/download`;
}

export function obtenerUrlArchivoReporte(
  executionId: number,
  name: string,
): string {
  return `${BASE_URL}/reports/${executionId}/reports/${name}.csv`;
}

export function listarReportes(
  executionId: number,
): Promise<RespuestaListaReportes> {
  return peticionJson<RespuestaListaReportes>(
    `/reports/${executionId}/reports`,
  );
}

export async function descargarReporte(
  url: string,
  filename: string,
): Promise<void> {
  const response = await fetch(url, { headers: { ...cabecerasAuth() } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Error al descargar (${response.status})`);
  }
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
}
