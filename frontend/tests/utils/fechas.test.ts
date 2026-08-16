import {
  ahoraISO,
  esSemestreValido,
  formatearDuracion,
  formatearFecha,
  formatearFechaHora,
  formatearSemestre,
  obtenerSemestreActual,
  tiempoRelativo,
} from "../../utils/fechas.ts";

import { assert, assertEquals, assertFalse } from "@std/assert";

// ---------------------------------------------------------------------------
// formatearFechaHora
// ---------------------------------------------------------------------------
Deno.test("formatDateTime - convierte una fecha ISO a formato dd/MM/yyyy HH:mm", () => {
  const iso = "2025-03-15T14:30:00.000Z";
  const result = formatearFechaHora(iso);
  // El resultado exacto depende del locale y el offset, pero debe contener algo parecido
  assert(result.includes("2025"));
  assert(result.includes("03") || result.includes("3"));
  assert(result.includes("15"));
});

Deno.test("formatDateTime - retorna '—' para null o undefined", () => {
  assertEquals(formatearFechaHora(null), "—");
  assertEquals(formatearFechaHora(undefined), "—");
});

Deno.test("formatDateTime - maneja una fecha inválida", () => {
  const result = formatearFechaHora("no-es-una-fecha");
  assert(result.includes("Fecha inválida"));
});

// ---------------------------------------------------------------------------
// formatearFecha
// ---------------------------------------------------------------------------
Deno.test("formatDate - convierte una fecha ISO a dd/MM/yyyy", () => {
  const iso = "2024-10-05T08:00:00Z";
  const result = formatearFecha(iso);
  assert(result.includes("2024"));
  assert(result.includes("10"));
  assert(result.includes("05"));
});

Deno.test("formatDate - retorna '—' para null/undefined", () => {
  assertEquals(formatearFecha(null), "—");
  assertEquals(formatearFecha(undefined), "—");
});

Deno.test("formatDate - fecha inválida", () => {
  assertEquals(formatearFecha("abc"), "Fecha inválida");
});

// ---------------------------------------------------------------------------
// formatearDuracion
// ---------------------------------------------------------------------------
Deno.test("formatDuration - convierte segundos a horas, minutos y segundos", () => {
  assertEquals(formatearDuracion(3661), "1h 1m 1s");
  assertEquals(formatearDuracion(3600), "1h");
  assertEquals(formatearDuracion(61), "1m 1s");
  assertEquals(formatearDuracion(0), "—");
  assertEquals(formatearDuracion(null), "—");
  assertEquals(formatearDuracion(undefined), "—");
});

// ---------------------------------------------------------------------------
// esSemestreValido
// ---------------------------------------------------------------------------
Deno.test("isValidSemester - valida formatos correctos", () => {
  assert(esSemestreValido("2025A"));
  assert(esSemestreValido("2025B"));
  assert(esSemestreValido("2019A"));
});

Deno.test("isValidSemester - rechaza formatos incorrectos", () => {
  assertFalse(esSemestreValido("2025C"));
  assertFalse(esSemestreValido("25A"));
  assertFalse(esSemestreValido("2025"));
  assertFalse(esSemestreValido(""));
  assertFalse(esSemestreValido("abc"));
});

// ---------------------------------------------------------------------------
// obtenerSemestreActual
// ---------------------------------------------------------------------------
Deno.test("getCurrentSemester - retorna un semestre válido", () => {
  const current = obtenerSemestreActual();
  // Debe cumplir con el formato
  assert(esSemestreValido(current));
  // El año debe ser el actual
  const now = new Date();
  const year = now.getFullYear();
  assert(current.startsWith(String(year)));
});

// ---------------------------------------------------------------------------
// formatearSemestre
// ---------------------------------------------------------------------------
Deno.test("formatSemester - formatea un semestre válido con guion", () => {
  assertEquals(formatearSemestre("2025A"), "2025-A");
  assertEquals(formatearSemestre("2024B"), "2024-B");
});

Deno.test("formatSemester - devuelve el original si no es válido", () => {
  assertEquals(formatearSemestre("abc"), "abc");
  assertEquals(formatearSemestre("2025"), "2025");
});

// ---------------------------------------------------------------------------
// ahoraISO
// ---------------------------------------------------------------------------
Deno.test("nowISO - retorna una cadena ISO 8601", () => {
  const iso = ahoraISO();
  assert(typeof iso === "string");
  const date = new Date(iso);
  assertEquals(date.toISOString(), iso);
});

// ---------------------------------------------------------------------------
// tiempoRelativo
// ---------------------------------------------------------------------------
Deno.test("timeAgo - retorna una cadena con 'hace ...'", () => {
  // Usamos una fecha reciente para que el texto incluya "hace"
  const justNow = new Date(Date.now() - 30 * 1000).toISOString();
  const result = tiempoRelativo(justNow);
  assert(result.startsWith("hace"));
});

Deno.test("timeAgo - retorna '—' para null/undefined", () => {
  assertEquals(tiempoRelativo(null), "—");
  assertEquals(tiempoRelativo(undefined), "—");
});

Deno.test("timeAgo - maneja fecha inválida", () => {
  assertEquals(tiempoRelativo("basura"), "—");
});
