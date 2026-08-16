import {
  formatDate,
  formatDateTime,
  formatDuration,
  formatSemester,
  getCurrentSemester,
  isValidSemester,
  nowISO,
  timeAgo,
} from "../../utils/date.ts";

import { assert, assertEquals, assertFalse } from "@std/assert";

// ---------------------------------------------------------------------------
// formatDateTime
// ---------------------------------------------------------------------------
Deno.test("formatDateTime - convierte una fecha ISO a formato dd/MM/yyyy HH:mm", () => {
  const iso = "2025-03-15T14:30:00.000Z";
  const result = formatDateTime(iso);
  // El resultado exacto depende del locale y el offset, pero debe contener algo parecido
  assert(result.includes("2025"));
  assert(result.includes("03") || result.includes("3"));
  assert(result.includes("15"));
});

Deno.test("formatDateTime - retorna '—' para null o undefined", () => {
  assertEquals(formatDateTime(null), "—");
  assertEquals(formatDateTime(undefined), "—");
});

Deno.test("formatDateTime - maneja una fecha inválida", () => {
  const result = formatDateTime("no-es-una-fecha");
  assert(result.includes("Fecha inválida"));
});

// ---------------------------------------------------------------------------
// formatDate
// ---------------------------------------------------------------------------
Deno.test("formatDate - convierte una fecha ISO a dd/MM/yyyy", () => {
  const iso = "2024-10-05T08:00:00Z";
  const result = formatDate(iso);
  assert(result.includes("2024"));
  assert(result.includes("10"));
  assert(result.includes("05"));
});

Deno.test("formatDate - retorna '—' para null/undefined", () => {
  assertEquals(formatDate(null), "—");
  assertEquals(formatDate(undefined), "—");
});

Deno.test("formatDate - fecha inválida", () => {
  assertEquals(formatDate("abc"), "Fecha inválida");
});

// ---------------------------------------------------------------------------
// formatDuration
// ---------------------------------------------------------------------------
Deno.test("formatDuration - convierte segundos a horas, minutos y segundos", () => {
  assertEquals(formatDuration(3661), "1h 1m 1s");
  assertEquals(formatDuration(3600), "1h");
  assertEquals(formatDuration(61), "1m 1s");
  assertEquals(formatDuration(0), "—");
  assertEquals(formatDuration(null), "—");
  assertEquals(formatDuration(undefined), "—");
});

// ---------------------------------------------------------------------------
// isValidSemester
// ---------------------------------------------------------------------------
Deno.test("isValidSemester - valida formatos correctos", () => {
  assert(isValidSemester("2025A"));
  assert(isValidSemester("2025B"));
  assert(isValidSemester("2019A"));
});

Deno.test("isValidSemester - rechaza formatos incorrectos", () => {
  assertFalse(isValidSemester("2025C"));
  assertFalse(isValidSemester("25A"));
  assertFalse(isValidSemester("2025"));
  assertFalse(isValidSemester(""));
  assertFalse(isValidSemester("abc"));
});

// ---------------------------------------------------------------------------
// getCurrentSemester
// ---------------------------------------------------------------------------
Deno.test("getCurrentSemester - retorna un semestre válido", () => {
  const current = getCurrentSemester();
  // Debe cumplir con el formato
  assert(isValidSemester(current));
  // El año debe ser el actual
  const now = new Date();
  const year = now.getFullYear();
  assert(current.startsWith(String(year)));
});

// ---------------------------------------------------------------------------
// formatSemester
// ---------------------------------------------------------------------------
Deno.test("formatSemester - formatea un semestre válido con guion", () => {
  assertEquals(formatSemester("2025A"), "2025-A");
  assertEquals(formatSemester("2024B"), "2024-B");
});

Deno.test("formatSemester - devuelve el original si no es válido", () => {
  assertEquals(formatSemester("abc"), "abc");
  assertEquals(formatSemester("2025"), "2025");
});

// ---------------------------------------------------------------------------
// nowISO
// ---------------------------------------------------------------------------
Deno.test("nowISO - retorna una cadena ISO 8601", () => {
  const iso = nowISO();
  assert(typeof iso === "string");
  const date = new Date(iso);
  assertEquals(date.toISOString(), iso);
});

// ---------------------------------------------------------------------------
// timeAgo
// ---------------------------------------------------------------------------
Deno.test("timeAgo - retorna una cadena con 'hace ...'", () => {
  // Usamos una fecha reciente para que el texto incluya "hace"
  const justNow = new Date(Date.now() - 30 * 1000).toISOString();
  const result = timeAgo(justNow);
  assert(result.startsWith("hace"));
});

Deno.test("timeAgo - retorna '—' para null/undefined", () => {
  assertEquals(timeAgo(null), "—");
  assertEquals(timeAgo(undefined), "—");
});

Deno.test("timeAgo - maneja fecha inválida", () => {
  assertEquals(timeAgo("basura"), "—");
});
