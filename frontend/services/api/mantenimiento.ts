// services/api/mantenimiento.ts
import { BASE_URL, authHeaders, handleResponse } from "./core.ts";
import type { CsvUploadResponse } from "./types.ts";

export async function uploadVisibilityCsv(
  file: File,
  visibility: "show" | "hide",
): Promise<CsvUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(
    `${BASE_URL}/operations/courses/visibility?visibility=${visibility}`,
    { method: "POST", headers: { ...authHeaders() }, body: formData },
  );
  return handleResponse<CsvUploadResponse>(response);
}
