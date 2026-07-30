import { authHeaders, BASE_URL, handleResponse } from "./core.ts";
import type { ApplyNovedadesResponse, NovedadesResponse } from "./types.ts";

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

export async function applyNovedades(
  semester: string,
  novedades: Array<{
    id: string;
    action: string;
    old_shortname: string;
    new_shortname: string;
    course_fullname: string;
    category_idnumber?: string;
    new_prof_username?: string;
    new_prof_cedula?: string;
  }>,
): Promise<ApplyNovedadesResponse> {
  const response = await fetch(`${BASE_URL}/novedades/apply`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ semester, novedades }),
  });
  return handleResponse<ApplyNovedadesResponse>(response);
}
