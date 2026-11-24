// services/api/trabajos.ts
import { peticionJson } from "./nucleo.ts";
import type { Ejecucion, RegistroError } from "./tipos.ts";

export async function obtenerSemestreActual(): Promise<string> {
  const data = await peticionJson<{ semester: string }>("/upload/current");
  return data.semester;
}

export interface EstadoSubida {
  allowed: boolean;
  execution: { id: number; status: string; filename: string } | null;
  batch: { batch_id: string; entity_type: string; action: string } | null;
}

export function obtenerEstadoSubida(
  modalidad?: string,
): Promise<EstadoSubida> {
  return peticionJson<EstadoSubida>("/upload/status", {
    params: { modalidad },
  });
}

export function subirArchivo(
  file: File,
  semester: string,
  modalidad: string,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("semester", semester);
  formData.append("modalidad", modalidad);
  return peticionJson<{
    execution_id: number;
    filename: string;
    semester: string;
    mode: string;
    status: string;
    message: string;
  }>("/upload", { method: "POST", form: formData });
}

type RespuestaAccionTrabajo = {
  execution_id: number;
  job_id: string;
  status: string;
  message: string;
};

function accionTrabajo(
  executionId: number,
  accion: "process" | "confirm" | "pause" | "cancel",
): Promise<RespuestaAccionTrabajo> {
  return peticionJson<RespuestaAccionTrabajo>(
    `/jobs/${executionId}/${accion}`,
    { method: "POST" },
  );
}

export function iniciarProceso(executionId: number) {
  return accionTrabajo(executionId, "process");
}

export function obtenerEjecucion(
  executionId: number,
): Promise<Ejecucion> {
  return peticionJson<Ejecucion>(`/jobs/${executionId}`);
}

export function listarEjecuciones(params: {
  semester?: string;
  status?: string;
  mode?: string;
  modalidad?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<{ total: number; items: Ejecucion[] }> {
  return peticionJson<{ total: number; items: Ejecucion[] }>("/jobs", {
    params: {
      semester: params.semester,
      status: params.status,
      mode: params.mode,
      modalidad: params.modalidad,
      limit: params.limit || undefined,
      offset: params.offset || undefined,
    },
  });
}

export function obtenerErroresEjecucion(
  executionId: number,
  limit = 100,
  offset = 0,
): Promise<RegistroError[]> {
  return peticionJson<RegistroError[]>(`/jobs/${executionId}/errors`, {
    params: { limit, offset },
  });
}

export async function eliminarEjecucion(executionId: number): Promise<void> {
  await peticionJson<void>(`/jobs/${executionId}`, { method: "DELETE" });
}

export function confirmarEjecucion(executionId: number) {
  return accionTrabajo(executionId, "confirm");
}

// Reusa /process porque el backend acepta status "paused" y reanuda desde checkpoint
export const reanudarEjecucion = iniciarProceso;

export function pausarEjecucion(executionId: number) {
  return accionTrabajo(executionId, "pause");
}

export function cancelarEjecucion(executionId: number) {
  return accionTrabajo(executionId, "cancel");
}
