// services/api/operaciones.ts
import { BASE_URL, peticionJson } from "./nucleo.ts";
import type {
  EstadoLoteOperacion,
  ItemHistorialOperaciones,
  LoteOperacionSalida,
  RespuestaSubidaCsv,
} from "./tipos.ts";

export function subirArchivoCsv(
  endpoint: string,
  file: File,
): Promise<RespuestaSubidaCsv> {
  const formData = new FormData();
  formData.append("file", file);
  return peticionJson<RespuestaSubidaCsv>(`/operations/${endpoint}`, {
    method: "POST",
    form: formData,
  });
}

export function obtenerEstadoLote(
  batchId: string,
  offset = 0,
  limit = 100,
): Promise<EstadoLoteOperacion> {
  return peticionJson<EstadoLoteOperacion>(
    `/operations/batch/${batchId}/status`,
    { params: { offset, limit } },
  );
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

export function listarLotes(params: {
  entity_type?: string;
  action?: string;
  modalidad?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<{ total: number; items: LoteOperacionSalida[] }> {
  return peticionJson<{ total: number; items: LoteOperacionSalida[] }>(
    "/operations/batches",
    {
      params: {
        entity_type: params.entity_type,
        action: params.action,
        modalidad: params.modalidad,
        limit: params.limit || undefined,
        offset: params.offset || undefined,
      },
    },
  );
}

export async function obtenerAnaliticaOperaciones(
  modalidad?: string,
  months = 12,
  entityType?: string,
  action?: string,
): Promise<ItemHistorialOperaciones[]> {
  const data = await peticionJson<{ history: ItemHistorialOperaciones[] }>(
    "/operations/analytics",
    {
      params: {
        months,
        modalidad,
        entity_type: entityType,
        action,
      },
    },
  );
  return data.history;
}

export function pausarLote(batchId: string) {
  return peticionJson<{ batch_id: string; paused: number; message: string }>(
    `/operations/batch/${batchId}/pause`,
    { method: "POST" },
  );
}

export function reanudarLote(batchId: string) {
  return peticionJson<{ batch_id: string; resumed: number; message: string }>(
    `/operations/batch/${batchId}/resume`,
    { method: "POST" },
  );
}

export function cancelarLote(batchId: string) {
  return peticionJson<{ batch_id: string; cancelled: number; message: string }>(
    `/operations/batch/${batchId}/cancel`,
    { method: "POST" },
  );
}

export async function eliminarLote(batchId: string) {
  await peticionJson<unknown>(`/operations/batch/${batchId}`, {
    method: "DELETE",
  });
}
