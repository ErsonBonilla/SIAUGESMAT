import { render } from "preact-render-to-string";
import { assert, assertStringIncludes } from "@std/assert";

import FormularioLogin from "../../islands/FormularioLogin.tsx";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("FormularioLogin - muestra selector de modalidad sin campos de login", () => {
  darkSignal.value = false;
  const html = render(
    <FormularioLogin modalidad="" onModalidadChange={() => {}} />,
  );

  assertStringIncludes(html, "PRESENCIAL");
  assertStringIncludes(html, "DISTANCIA");
  assertStringIncludes(html, "Seleccioná tu modalidad");

  assert(!html.includes("Usuario"), "no debe mostrar Usuario sin modalidad");
});

Deno.test("FormularioLogin - muestra campos de login cuando se selecciona modalidad", () => {
  darkSignal.value = false;
  const html = render(
    <FormularioLogin modalidad="DISTANCIA" onModalidadChange={() => {}} />,
  );

  assertStringIncludes(html, "Usuario");
  assertStringIncludes(html, "Contraseña");
  assertStringIncludes(html, "Iniciar sesión");
});
