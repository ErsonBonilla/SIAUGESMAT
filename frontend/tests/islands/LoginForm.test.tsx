import render from "preact-render-to-string";
import { assertStringIncludes, assert } from "https://deno.land/std@0.224.0/assert/mod.ts";

import LoginForm from "../../islands/LoginForm.tsx";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("LoginForm - muestra selector de modalidad sin campos de login", () => {
  darkSignal.value = false;
  const html = render(<LoginForm modalidad="" onModalidadChange={() => {}} />);

  assertStringIncludes(html, "PRESENCIAL");
  assertStringIncludes(html, "DISTANCIA");
  assertStringIncludes(html, "Seleccioná tu modalidad");

  assert(!html.includes("Usuario"), "no debe mostrar Usuario sin modalidad");
});

Deno.test("LoginForm - muestra campos de login cuando se selecciona modalidad", () => {
  darkSignal.value = false;
  const html = render(<LoginForm modalidad="DISTANCIA" onModalidadChange={() => {}} />);

  assertStringIncludes(html, "Usuario");
  assertStringIncludes(html, "Contraseña");
  assertStringIncludes(html, "Iniciar sesión");
});
