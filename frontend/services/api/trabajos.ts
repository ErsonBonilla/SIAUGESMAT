// services/api/trabajos.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type { Ejecucion, RegistroError } from "./tipos.ts";

export async function obtenerSemestreActual(): Promise<string> {
  const response = await fetch(`${BASE_URL}/upload/current`, {
    headers: { ...cabecerasAuth() },
  });
  const data = await manejarRespuesta<{ semester: string }>(response);
  return data.semester;
}

export interface EstadoSubida {
  allowed: boolean;
  execution: { id: number; status: string; filename: string } | null;
  batch: { batch_id: string; entity_type: string; action: string } | null;
}

export async function obtenerEstadoSubida(
  modalidad?: string,
): Promise<EstadoSubida> {
  const sp = new URLSearchParams();
  if (modalidad) sp.set("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/upload/status?${sp}`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<EstadoSubida>(response);
}

export async function subirArchivo(
  file: File,
  semester: string,
  modalidad: string,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("semester", semester);
  formData.append("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
    body: formData,
  });
  return manejarRespuesta<
    {
      execution_id: number;
      filename: string;
      semester: string;
      mode: string;
      status: string;
      message: string;
    }
  >(response);
}

export async function iniciarProceso(executionId: number) {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/process`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<
    { execution_id: number; job_id: string; status: string; message: string }
  >(response);
}

export async function obtenerEjecucion(
  executionId: number,
): Promise<Ejecucion> {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<Ejecucion>(response);
}

export async function listarEjecuciones(params: {
  semester?: string;
  status?: string;
  mode?: string;
  modalidad?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<{ total: number; items: Ejecucion[] }> {
  const sp = new URLSearchParams();
  if (params.semester) sp.set("semester", params.semester);
  if (params.status) sp.set("status", params.status);
  if (params.mode) sp.set("mode", params.mode);
  if (params.modalidad) sp.set("modalidad", params.modalidad);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  const response = await fetch(`${BASE_URL}/jobs?${sp}`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<{ total: number; items: Ejecucion[] }>(response);
}

export async function obtenerErroresEjecucion(
  executionId: number,
  limit = 100,
  offset = 0,
): Promise<RegistroError[]> {
  const response = await fetch(
    `${BASE_URL}/jobs/${executionId}/errors?limit=${limit}&offset=${offset}`,
    { headers: { ...cabecerasAuth() } },
  );
  return manejarRespuesta<RegistroError[]>(response);
}

export async function eliminarEjecucion(executionId: number): Promise<void> {
  await manejarRespuesta(
    await fetch(`${BASE_URL}/jobs/${executionId}`, {
      method: "DELETE",
      headers: { ...cabecerasAuth() },
    }),
  );
}

export async function confirmarEjecucion(executionId: number) {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/confirm`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<
    { execution_id: number; job_id: string; status: string; message: string }
  >(response);
}

// Reusa /process porque el backend acepta status "paused" y reanuda desde checkpoint
export const reanudarEjecucion = iniciarProceso;

export async function pausarEjecucion(executionId: number) {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/pause`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<
    { execution_id: number; job_id: string; status: string; message: string }
  >(response);
}

export async function cancelarEjecucion(executionId: number) {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/cancel`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<
    { execution_id: number; job_id: string; status: string; message: string }
  >(response);
}
