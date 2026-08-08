import { render } from "preact-render-to-string";
import { assertStringIncludes } from "@std/assert";

import Chart from "../../islands/GraficoIsland.tsx";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("Chart - renderiza contenedor con título", () => {
  darkSignal.value = false;
  const html = render(
    <Chart
      executionId={1}
      chartName="resumen_operaciones"
      title="Resumen de operaciones"
    />,
  );

  assertStringIncludes(html, "Resumen de operaciones");
  assertStringIncludes(html, 'id="chart-resumen_operaciones-1"');
});

Deno.test("Chart - renderiza sin título", () => {
  darkSignal.value = false;
  const html = render(
    <Chart executionId={2} chartName="distribucion_incidencias" />,
  );

  assertStringIncludes(html, 'id="chart-distribucion_incidencias-2"');
});

Deno.test("Chart - usa height personalizado", () => {
  darkSignal.value = true;
  const html = render(
    <Chart executionId={3} chartName="cursos_por_accion" height="500px" />,
  );

  assertStringIncludes(html, "height:500px");
});
