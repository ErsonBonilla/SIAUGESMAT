import {
  getToken,
  getTokenPayload,
  getUsername,
  isTokenValid,
  removeToken,
  setToken,
} from "../../utils/auth.ts";
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
  assertEquals(getToken(), null);
});
Deno.test("setToken y getToken - guarda y recupera el token", () => {
  localStorage.clear();
  setToken("mi-super-token");
  assertEquals(getToken(), "mi-super-token");
});
Deno.test("removeToken - elimina el token", () => {
  localStorage.clear();
  setToken("otro-token");
  removeToken();
  assertEquals(getToken(), null);
});
Deno.test("isTokenValid - false si no hay token", () => {
  localStorage.clear();
  assertFalse(isTokenValid());
});
Deno.test("isTokenValid - true con token no expirado", () => {
  localStorage.clear();
  setToken(makeToken({ exp: Math.floor(Date.now() / 1000) + 3600 }));
  assert(isTokenValid());
});
Deno.test("isTokenValid - false con token expirado", () => {
  localStorage.clear();
  setToken(makeToken({ exp: Math.floor(Date.now() / 1000) - 60 }));
  assertFalse(isTokenValid());
});
Deno.test("isTokenValid - true si no hay campo exp", () => {
  localStorage.clear();
  setToken(makeToken({ username: "test" }));
  assert(isTokenValid());
});
Deno.test("getTokenPayload - retorna payload decodificado", () => {
  localStorage.clear();
  setToken(makeToken({ username: "juan", role: "admin" }));
  const decoded = getTokenPayload();
  assertExists(decoded);
  assertEquals(decoded!.username, "juan");
});
Deno.test("getTokenPayload - retorna null si no hay token", () => {
  localStorage.clear();
  assertEquals(getTokenPayload(), null);
});
Deno.test("getUsername - retorna el username del token", () => {
  localStorage.clear();
  setToken(makeToken({ username: "profesor_perez" }));
  assertEquals(getUsername(), "profesor_perez");
});
Deno.test("getUsername - retorna null si no hay token", () => {
  localStorage.clear();
  assertEquals(getUsername(), null);
});
Deno.test("decodifica base64url con '_'/'-' y caracteres UTF-8", () => {
  // El username contiene "/" y "año": al codificar en base64url aparece "_"
  // y los bytes multibyte requieren decodificación UTF-8 (atob directo falla).
  localStorage.clear();
  setToken(makeToken({ username: "profe/paño" }));
  assertEquals(getUsername(), "profe/paño");
  assert(isTokenValid());
});
