// services/api/reports.ts
import { BASE_URL, authHeaders, handleResponse } from "./core.ts";
import type { ReportsListResponse } from "./types.ts";

export async function listReports(executionId: number): Promise<ReportsListResponse> {
  const response = await fetch(`${BASE_URL}/reports/${executionId}/reports`, { headers: { ...authHeaders() } });
  return handleResponse<ReportsListResponse>(response);
}

export async function downloadReport(url: string, filename: string): Promise<void> {
  const response = await fetch(url, { headers: { ...authHeaders() } });
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
