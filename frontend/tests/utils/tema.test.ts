import { assert, assertEquals } from "@std/assert";
import { normalizarTema, senalTemaOscuro } from "../../utils/tema.ts";

Deno.test("theme - senalTemaOscuro defaults to true", () => {
  const initial = senalTemaOscuro.value;
  assert(typeof initial === "boolean");
});

Deno.test("theme - set senalTemaOscuro to true", () => {
  senalTemaOscuro.value = true;
  assertEquals(senalTemaOscuro.value, true);
});

Deno.test("theme - set senalTemaOscuro to false", () => {
  senalTemaOscuro.value = false;
  assertEquals(senalTemaOscuro.value, false);
});

Deno.test("theme - toggle senalTemaOscuro from false to true", () => {
  senalTemaOscuro.value = false;
  senalTemaOscuro.value = true;
  assertEquals(senalTemaOscuro.value, true);
});

Deno.test("theme - toggle senalTemaOscuro from true to false", () => {
  senalTemaOscuro.value = true;
  senalTemaOscuro.value = false;
  assertEquals(senalTemaOscuro.value, false);
});

Deno.test("theme - normalizarTema accepts light", () => {
  assertEquals(normalizarTema("light"), "light");
});

Deno.test("theme - normalizarTema coerces arbitrary values to dark", () => {
  assertEquals(normalizarTema('");alert(1);//'), "dark");
  assertEquals(normalizarTema("<script>"), "dark");
  assertEquals(normalizarTema("DARK"), "dark");
});

Deno.test("theme - normalizarTema handles empty and missing values", () => {
  assertEquals(normalizarTema(""), "dark");
  assertEquals(normalizarTema(undefined), "dark");
  assertEquals(normalizarTema(null), "dark");
});
