// services/api/consultas.ts
import { BASE_URL, peticionJson } from "./nucleo.ts";
import type { EstadoTareaConsulta } from "./tipos.ts";

export function consultarEntidades(
  entity: string,
  params: Record<string, string> = {},
) {
  return peticionJson<{ task_id: string; status: string; message: string }>(
    `/queries/${entity}`,
    { method: "POST", json: params },
  );
}

export function obtenerEstadoTareaConsulta(
  taskId: string,
): Promise<EstadoTareaConsulta> {
  return peticionJson<EstadoTareaConsulta>(`/queries/tasks/${taskId}`);
}

export function obtenerUrlExportarConsulta(taskId: string): string {
  return `${BASE_URL}/queries/tasks/${taskId}/download`;
}
