import { render } from "preact-render-to-string";
import { assertEquals, assertStringIncludes } from "@std/assert";

import AlternadorTema from "../../islands/AlternadorTema.tsx";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("AlternadorTema - renders sun icon in dark mode", () => {
  darkSignal.value = true;
  const html = render(<AlternadorTema />);

  assertStringIncludes(html, "Cambiar a modo claro");
  assertEquals(darkSignal.value, true);
});

Deno.test("AlternadorTema - renders moon icon in light mode", () => {
  darkSignal.value = false;
  const html = render(<AlternadorTema />);

  assertStringIncludes(html, "Cambiar a modo oscuro");
  assertEquals(darkSignal.value, false);
});
