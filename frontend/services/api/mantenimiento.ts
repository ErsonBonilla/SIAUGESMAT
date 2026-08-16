// services/api/mantenimiento.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type { RespuestaSubidaCsv } from "./tipos.ts";

export async function subirCsvVisibilidad(
  file: File,
  visibility: "show" | "hide",
): Promise<RespuestaSubidaCsv> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(
    `${BASE_URL}/operations/courses/visibility?visibility=${visibility}`,
    { method: "POST", headers: { ...cabecerasAuth() }, body: formData },
  );
  return manejarRespuesta<RespuestaSubidaCsv>(response);
}
