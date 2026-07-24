// services/api/jobs.ts
import { BASE_URL, authHeaders, handleResponse } from "./core.ts";
import type { Execution, ErrorLog } from "./types.ts";

export async function getCurrentSemester(): Promise<string> {
  const response = await fetch(`${BASE_URL}/upload/current`, { headers: { ...authHeaders() } });
  const data = await handleResponse<{ semester: string }>(response);
  return data.semester;
}

export async function uploadFile(file: File, semester: string, modalidad: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("semester", semester);
  formData.append("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });
  return handleResponse<{ execution_id: number; filename: string; semester: string; mode: string; status: string; message: string }>(response);
}

export async function startProcess(executionId: number) {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/process`, {
    method: "POST",
    headers: { ...authHeaders() },
  });
  return handleResponse<{ execution_id: number; job_id: string; status: string; message: string }>(response);
}

export async function getExecution(executionId: number): Promise<Execution> {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}`, { headers: { ...authHeaders() } });
  return handleResponse<Execution>(response);
}

export async function listExecutions(params: {
  semester?: string; status?: string; mode?: string; modalidad?: string; limit?: number; offset?: number;
} = {}): Promise<{ total: number; items: Execution[] }> {
  const sp = new URLSearchParams();
  if (params.semester) sp.set("semester", params.semester);
  if (params.status) sp.set("status", params.status);
  if (params.mode) sp.set("mode", params.mode);
  if (params.modalidad) sp.set("modalidad", params.modalidad);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  const response = await fetch(`${BASE_URL}/jobs?${sp}`, { headers: { ...authHeaders() } });
  return handleResponse<{ total: number; items: Execution[] }>(response);
}

export async function getExecutionErrors(executionId: number, limit = 100, offset = 0): Promise<ErrorLog[]> {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/errors?limit=${limit}&offset=${offset}`, { headers: { ...authHeaders() } });
  return handleResponse<ErrorLog[]>(response);
}

export async function deleteExecution(executionId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}`, { method: "DELETE", headers: { ...authHeaders() } });
  if (!response.ok) await handleResponse<unknown>(response);
}

export async function confirmExecution(executionId: number) {
  const response = await fetch(`${BASE_URL}/jobs/${executionId}/confirm`, {
    method: "POST",
    headers: { ...authHeaders() },
  });
  return handleResponse<{ execution_id: number; job_id: string; status: string; message: string }>(response);
}
