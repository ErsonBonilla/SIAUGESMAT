// services/api/operaciones.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type {
  EstadoLoteOperacion,
  ItemHistorialOperaciones,
  LoteOperacionSalida,
  RespuestaSubidaCsv,
} from "./tipos.ts";

export async function subirArchivoCsv(
  endpoint: string,
  file: File,
): Promise<RespuestaSubidaCsv> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${BASE_URL}/operations/${endpoint}`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
    body: formData,
  });
  return manejarRespuesta<RespuestaSubidaCsv>(response);
}

export async function obtenerEstadoLote(
  batchId: string,
  offset = 0,
  limit = 100,
): Promise<EstadoLoteOperacion> {
  const response = await fetch(
    `${BASE_URL}/operations/batch/${batchId}/status?offset=${offset}&limit=${limit}`,
    { headers: { ...cabecerasAuth() } },
  );
  return manejarRespuesta<EstadoLoteOperacion>(response);
}

export function obtenerUrlDescargaReporteLote(batchId: string): string {
  return `${BASE_URL}/operations/batch/${batchId}/reports/download`;
}

export function obtenerUrlArchivoReporteLote(
  batchId: string,
  reportName: string,
): string {
  return `${BASE_URL}/operations/batch/${batchId}/reports/${reportName}`;
}

export async function listarLotes(params: {
  entity_type?: string;
  action?: string;
  modalidad?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<{ total: number; items: LoteOperacionSalida[] }> {
  const sp = new URLSearchParams();
  if (params.entity_type) sp.set("entity_type", params.entity_type);
  if (params.action) sp.set("action", params.action);
  if (params.modalidad) sp.set("modalidad", params.modalidad);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  const response = await fetch(`${BASE_URL}/operations/batches?${sp}`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<{ total: number; items: LoteOperacionSalida[] }>(
    response,
  );
}

export async function obtenerAnaliticaOperaciones(
  modalidad?: string,
  months = 12,
  entityType?: string,
  action?: string,
): Promise<ItemHistorialOperaciones[]> {
  const params = new URLSearchParams({ months: String(months) });
  if (modalidad) params.set("modalidad", modalidad);
  if (entityType) params.set("entity_type", entityType);
  if (action) params.set("action", action);
  const response = await fetch(`${BASE_URL}/operations/analytics?${params}`, {
    headers: { ...cabecerasAuth() },
  });
  const data = await manejarRespuesta<{ history: ItemHistorialOperaciones[] }>(
    response,
  );
  return data.history;
}

export async function pausarLote(batchId: string) {
  const response = await fetch(
    `${BASE_URL}/operations/batch/${batchId}/pause`,
    {
      method: "POST",
      headers: { ...cabecerasAuth() },
    },
  );
  return manejarRespuesta<
    { batch_id: string; paused: number; message: string }
  >(
    response,
  );
}

export async function reanudarLote(batchId: string) {
  const response = await fetch(
    `${BASE_URL}/operations/batch/${batchId}/resume`,
    {
      method: "POST",
      headers: { ...cabecerasAuth() },
    },
  );
  return manejarRespuesta<
    { batch_id: string; resumed: number; message: string }
  >(
    response,
  );
}

export async function cancelarLote(batchId: string) {
  const response = await fetch(
    `${BASE_URL}/operations/batch/${batchId}/cancel`,
    {
      method: "POST",
      headers: { ...cabecerasAuth() },
    },
  );
  return manejarRespuesta<
    { batch_id: string; cancelled: number; message: string }
  >(
    response,
  );
}

export async function eliminarLote(batchId: string) {
  const response = await fetch(`${BASE_URL}/operations/batch/${batchId}`, {
    method: "DELETE",
    headers: { ...cabecerasAuth() },
  });
  if (!response.ok) await manejarRespuesta<unknown>(response);
}
