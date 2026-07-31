import { render } from "preact-render-to-string";
import { assert, assertStringIncludes } from "@std/assert";

import FileUploader from "../../islands/FileUploader.tsx";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("FileUploader - muestra el formulario de subida con todos los elementos", () => {
  darkSignal.value = false;
  const html = render(<FileUploader />);

  assertStringIncludes(html, "Archivo Excel");
  assertStringIncludes(html, "Subir y procesar archivo");
  assertStringIncludes(html, "Semestre");
  assertStringIncludes(html, "DISTANCIA");

  assert(!html.includes("Ambos"), "selector de modo eliminado");
  assert(!html.includes("Solo cursos"), "selector de modo eliminado");
  assert(!html.includes("Solo usuarios"), "selector de modo eliminado");
});
