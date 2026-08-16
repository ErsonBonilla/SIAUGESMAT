import {
  eliminarToken,
  esTokenValido,
  guardarToken,
  obtenerNombreUsuario,
  obtenerPayloadToken,
  obtenerToken,
} from "../../utils/autenticacion.ts";
import { assert, assertEquals, assertExists, assertFalse } from "@std/assert";

function base64urlEncode(str: string): string {
  // Codifica como UTF-8 (igual que python-jose) y luego a base64url.
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function makeToken(payload: Record<string, unknown>): string {
  const header = base64urlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  return `${header}.${base64urlEncode(JSON.stringify(payload))}.fakesignature`;
}

// localStorage existe como global en Deno (native Storage API).
// Cada test limpia el estado con clear() para aislamiento.

Deno.test("getToken - retorna null si no hay token", () => {
  localStorage.clear();
  assertEquals(obtenerToken(), null);
});
Deno.test("setToken y getToken - guarda y recupera el token", () => {
  localStorage.clear();
  guardarToken("mi-super-token");
  assertEquals(obtenerToken(), "mi-super-token");
});
Deno.test("removeToken - elimina el token", () => {
  localStorage.clear();
  guardarToken("otro-token");
  eliminarToken();
  assertEquals(obtenerToken(), null);
});
Deno.test("isTokenValid - false si no hay token", () => {
  localStorage.clear();
  assertFalse(esTokenValido());
});
Deno.test("isTokenValid - true con token no expirado", () => {
  localStorage.clear();
  guardarToken(makeToken({ exp: Math.floor(Date.now() / 1000) + 3600 }));
  assert(esTokenValido());
});
Deno.test("isTokenValid - false con token expirado", () => {
  localStorage.clear();
  guardarToken(makeToken({ exp: Math.floor(Date.now() / 1000) - 60 }));
  assertFalse(esTokenValido());
});
Deno.test("isTokenValid - true si no hay campo exp", () => {
  localStorage.clear();
  guardarToken(makeToken({ username: "test" }));
  assert(esTokenValido());
});
Deno.test("getTokenPayload - retorna payload decodificado", () => {
  localStorage.clear();
  guardarToken(makeToken({ username: "juan", role: "admin" }));
  const decoded = obtenerPayloadToken();
  assertExists(decoded);
  assertEquals(decoded!.username, "juan");
});
Deno.test("getTokenPayload - retorna null si no hay token", () => {
  localStorage.clear();
  assertEquals(obtenerPayloadToken(), null);
});
Deno.test("getUsername - retorna el username del token", () => {
  localStorage.clear();
  guardarToken(makeToken({ username: "profesor_perez" }));
  assertEquals(obtenerNombreUsuario(), "profesor_perez");
});
Deno.test("getUsername - retorna null si no hay token", () => {
  localStorage.clear();
  assertEquals(obtenerNombreUsuario(), null);
});
Deno.test("decodifica base64url con '_'/'-' y caracteres UTF-8", () => {
  // El username contiene "/" y "año": al codificar en base64url aparece "_"
  // y los bytes multibyte requieren decodificación UTF-8 (atob directo falla).
  localStorage.clear();
  guardarToken(makeToken({ username: "profe/paño" }));
  assertEquals(obtenerNombreUsuario(), "profe/paño");
  assert(esTokenValido());
});
