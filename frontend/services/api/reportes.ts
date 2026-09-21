// services/api/reportes.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
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

export async function listarReportes(
  executionId: number,
): Promise<RespuestaListaReportes> {
  const response = await fetch(`${BASE_URL}/reports/${executionId}/reports`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<RespuestaListaReportes>(response);
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
  URL.revokeObjectURL(blobUrl);
}
