import { render } from "preact-render-to-string";
import { assertStringIncludes } from "@std/assert";

import Grafico from "../../islands/GraficoIsland.tsx";
import { senalTemaOscuro } from "../../utils/tema.ts";

Deno.test("Chart - renderiza contenedor con título", () => {
  senalTemaOscuro.value = false;
  const html = render(
    <Grafico
      executionId={1}
      chartName="resumen_operaciones"
      title="Resumen de operaciones"
    />,
  );

  assertStringIncludes(html, "Resumen de operaciones");
  assertStringIncludes(html, 'id="chart-resumen_operaciones-1"');
});

Deno.test("Chart - renderiza sin título", () => {
  senalTemaOscuro.value = false;
  const html = render(
    <Grafico executionId={2} chartName="distribucion_incidencias" />,
  );

  assertStringIncludes(html, 'id="chart-distribucion_incidencias-2"');
});

Deno.test("Chart - usa height personalizado", () => {
  senalTemaOscuro.value = true;
  const html = render(
    <Grafico executionId={3} chartName="cursos_por_accion" height="500px" />,
  );

  assertStringIncludes(html, "height:500px");
});
