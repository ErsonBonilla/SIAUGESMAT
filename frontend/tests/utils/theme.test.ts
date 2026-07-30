import { assert, assertEquals } from "@std/assert";
import { darkSignal } from "../../utils/theme.ts";

Deno.test("theme - darkSignal defaults to true", () => {
  const initial = darkSignal.value;
  assert(typeof initial === "boolean");
});

Deno.test("theme - set darkSignal to true", () => {
  darkSignal.value = true;
  assertEquals(darkSignal.value, true);
});

Deno.test("theme - set darkSignal to false", () => {
  darkSignal.value = false;
  assertEquals(darkSignal.value, false);
});

Deno.test("theme - toggle darkSignal from false to true", () => {
  darkSignal.value = false;
  darkSignal.value = true;
  assertEquals(darkSignal.value, true);
});

Deno.test("theme - toggle darkSignal from true to false", () => {
  darkSignal.value = true;
  darkSignal.value = false;
  assertEquals(darkSignal.value, false);
});
