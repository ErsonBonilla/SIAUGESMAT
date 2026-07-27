// services/api/operations.ts
import { BASE_URL, authHeaders, handleResponse } from "./core.ts";
import type { CsvUploadResponse, OperationBatchStatus, OperationBatchOut, OperationsHistoryItem } from "./types.ts";

export async function uploadCsvFile(endpoint: string, file: File): Promise<CsvUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${BASE_URL}/operations/${endpoint}`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });
  return handleResponse<CsvUploadResponse>(response);
}

export async function getBatchStatus(batchId: string, offset = 0, limit = 100): Promise<OperationBatchStatus> {
  const response = await fetch(`${BASE_URL}/operations/batch/${batchId}/status?offset=${offset}&limit=${limit}`, { headers: { ...authHeaders() } });
  return handleResponse<OperationBatchStatus>(response);
}

export function getBatchReportUrl(batchId: string): string {
  return `${BASE_URL}/operations/batch/${batchId}/reports/download`;
}

export async function listBatches(params: {
  entity_type?: string; action?: string; modalidad?: string; limit?: number; offset?: number;
} = {}): Promise<{ total: number; items: OperationBatchOut[] }> {
  const sp = new URLSearchParams();
  if (params.entity_type) sp.set("entity_type", params.entity_type);
  if (params.action) sp.set("action", params.action);
  if (params.modalidad) sp.set("modalidad", params.modalidad);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  const response = await fetch(`${BASE_URL}/operations/batches?${sp}`, { headers: { ...authHeaders() } });
  return handleResponse<{ total: number; items: OperationBatchOut[] }>(response);
}

export async function getOperationsAnalytics(modalidad?: string, months = 12, entityType?: string, action?: string): Promise<OperationsHistoryItem[]> {
  const params = new URLSearchParams({ months: String(months) });
  if (modalidad) params.set("modalidad", modalidad);
  if (entityType) params.set("entity_type", entityType);
  if (action) params.set("action", action);
  const response = await fetch(`${BASE_URL}/operations/analytics?${params}`, { headers: { ...authHeaders() } });
  const data = await handleResponse<{ history: OperationsHistoryItem[] }>(response);
  return data.history;
}
