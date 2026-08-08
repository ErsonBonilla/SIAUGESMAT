import { render } from "preact-render-to-string";
import { assert, assertStringIncludes } from "@std/assert";

import FileUploader from "../../islands/FileUploader.tsx";
import ProcessInProgressBanner from "../../components/ProcessInProgressBanner.tsx";
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

Deno.test("ProcessInProgressBanner - muestra aviso cuando hay proceso en curso", () => {
  darkSignal.value = false;
  const html = render(
    <ProcessInProgressBanner
      status={{
        allowed: false,
        execution: { id: 3, status: "running", filename: "carga.xlsx" },
        batch: null,
      }}
    />,
  );

  assertStringIncludes(html, "No se pueden subir archivos");
  assertStringIncludes(html, "carga.xlsx");
});

Deno.test("ProcessInProgressBanner - no muestra nada si no hay proceso", () => {
  darkSignal.value = false;
  const html = render(
    <ProcessInProgressBanner
      status={{ allowed: true, execution: null, batch: null }}
    />,
  );
  assert(!html.includes("No se pueden subir archivos"));
});
