// services/api/reportes.ts
import { authHeaders, BASE_URL, handleResponse } from "./core.ts";
import type { ReportsListResponse } from "./types.ts";

export function getReportDownloadUrl(executionId: number): string {
  return `${BASE_URL}/reports/${executionId}/reports/download`;
}

export function getReportFileUrl(executionId: number, name: string): string {
  return `${BASE_URL}/reports/${executionId}/reports/${name}.csv`;
}

export async function listReports(
  executionId: number,
): Promise<ReportsListResponse> {
  const response = await fetch(`${BASE_URL}/reports/${executionId}/reports`, {
    headers: { ...authHeaders() },
  });
  return handleResponse<ReportsListResponse>(response);
}

export async function downloadReport(
  url: string,
  filename: string,
): Promise<void> {
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
