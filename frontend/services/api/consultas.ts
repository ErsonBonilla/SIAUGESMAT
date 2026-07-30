// services/api/consultas.ts
import { authHeaders, BASE_URL, handleResponse } from "./core.ts";
import type { QueryTaskStatus } from "./types.ts";

export async function queryEntities(
  entity: string,
  params: Record<string, string> = {},
) {
  const response = await fetch(`${BASE_URL}/queries/${entity}`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse<{ task_id: string; status: string; message: string }>(
    response,
  );
}

export async function getQueryTaskStatus(
  taskId: string,
): Promise<QueryTaskStatus> {
  const response = await fetch(`${BASE_URL}/queries/tasks/${taskId}`, {
    headers: { ...authHeaders() },
  });
  return handleResponse<QueryTaskStatus>(response);
}

export function getQueryExportUrl(taskId: string): string {
  return `${BASE_URL}/queries/tasks/${taskId}/download`;
}
