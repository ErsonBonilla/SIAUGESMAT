// services/api/consultas.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type { EstadoTareaConsulta } from "./tipos.ts";

export async function consultarEntidades(
  entity: string,
  params: Record<string, string> = {},
) {
  const response = await fetch(`${BASE_URL}/queries/${entity}`, {
    method: "POST",
    headers: { ...cabecerasAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return manejarRespuesta<{ task_id: string; status: string; message: string }>(
    response,
  );
}

export async function obtenerEstadoTareaConsulta(
  taskId: string,
): Promise<EstadoTareaConsulta> {
  const response = await fetch(`${BASE_URL}/queries/tasks/${taskId}`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<EstadoTareaConsulta>(response);
}

export function obtenerUrlExportarConsulta(taskId: string): string {
  return `${BASE_URL}/queries/tasks/${taskId}/download`;
}
