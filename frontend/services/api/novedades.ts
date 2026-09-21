import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type { RespuestaNovedades } from "./tipos.ts";

export async function compararNovedades(
  file: File,
  semester: string,
  modalidad: string,
): Promise<RespuestaNovedades> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("semester", semester);
  formData.append("modalidad", modalidad);
  const response = await fetch(`${BASE_URL}/novedades/compare`, {
    method: "POST",
    headers: { ...cabecerasAuth() },
    body: formData,
  });
  return manejarRespuesta<RespuestaNovedades>(response);
}
