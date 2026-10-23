import { render } from "preact-render-to-string";
import { assertEquals, assertStringIncludes } from "@std/assert";

import AlternadorTema from "../../islands/AlternadorTema.tsx";
import { senalTemaOscuro } from "../../utils/tema.ts";

Deno.test("AlternadorTema - renders sun icon in dark mode", () => {
  senalTemaOscuro.value = true;
  const html = render(<AlternadorTema />);

  assertStringIncludes(html, "Cambiar a modo claro");
  assertEquals(senalTemaOscuro.value, true);
});

Deno.test("AlternadorTema - renders moon icon in light mode", () => {
  senalTemaOscuro.value = false;
  const html = render(<AlternadorTema />);

  assertStringIncludes(html, "Cambiar a modo oscuro");
  assertEquals(senalTemaOscuro.value, false);
});
