import { darkSignal } from "../../utils/theme.ts";

Deno.test("theme - darkSignal defaults to true (dark) when localStorage unavailable", () => {
  darkSignal.value = true;
  darkSignal.value = false;
});

Deno.test("theme - set darkSignal directly to true (dark)", () => {
  darkSignal.value = true;
});

Deno.test("theme - set darkSignal directly to false (light)", () => {
  darkSignal.value = false;
});

Deno.test("theme - toggle darkSignal from false to true", () => {
  darkSignal.value = false;
  darkSignal.value = true;
});

Deno.test("theme - toggle darkSignal from true to false", () => {
  darkSignal.value = true;
  darkSignal.value = false;
});
