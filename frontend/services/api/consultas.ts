// services/api/consultas.ts
import { BASE_URL, peticionJson } from "./nucleo.ts";
import type { EstadoTareaConsulta, EstadoUltimoObservatorio } from "./tipos.ts";

export function obtenerUltimoObservatorio(): Promise<EstadoUltimoObservatorio> {
  return peticionJson<EstadoUltimoObservatorio>("/queries/observatorio/latest");
}

export function consultarEntidades(
  entity: string,
  params: Record<string, string> = {},
): Promise<{ task_id: string; status: string; message: string }> {
  return peticionJson<{ task_id: string; status: string; message: string }>(
    `/queries/${encodeURIComponent(entity)}`,
    { method: "POST", json: params },
  );
}

export function obtenerEstadoTareaConsulta<T = Record<string, unknown>[]>(
  taskId: string,
): Promise<EstadoTareaConsulta<T>> {
  return peticionJson<EstadoTareaConsulta<T>>(
    `/queries/tasks/${encodeURIComponent(taskId)}`,
  );
}

export function obtenerUrlExportarConsulta(taskId: string): string {
  return `${BASE_URL}/queries/tasks/${encodeURIComponent(taskId)}/download`;
}
