import { authHeaders, BASE_URL, handleResponse } from "./core.ts";
import type { NovedadesResponse } from "./types.ts";

export async function compareNovedades(
  file: File,
  semester: string,
  modalidad: string,
): Promise<NovedadesResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("semester", semester);
  formData.append("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/novedades/compare`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });
  return handleResponse<NovedadesResponse>(response);
}
