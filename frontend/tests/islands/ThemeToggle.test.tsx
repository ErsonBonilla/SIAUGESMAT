import render from "preact-render-to-string";
import { assertEquals, assertStringIncludes } from "https://deno.land/std@0.224.0/assert/mod.ts";

import ThemeToggle from "../../islands/ThemeToggle.tsx";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("ThemeToggle - renders sun icon in dark mode", () => {
  darkSignal.value = true;
  const html = render(<ThemeToggle />);

  assertStringIncludes(html, "Cambiar a modo claro");
  assertEquals(darkSignal.value, true);
});

Deno.test("ThemeToggle - renders moon icon in light mode", () => {
  darkSignal.value = false;
  const html = render(<ThemeToggle />);

  assertStringIncludes(html, "Cambiar a modo oscuro");
  assertEquals(darkSignal.value, false);
});
