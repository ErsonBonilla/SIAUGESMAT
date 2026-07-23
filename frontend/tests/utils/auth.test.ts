import {
  getToken,
  setToken,
  removeToken,
  isTokenValid,
  getTokenPayload,
  getUsername,
} from "../../utils/auth.ts";
import { assertEquals, assertExists, assertFalse, assert } from "https://deno.land/std@0.224.0/assert/mod.ts";

function base64urlEncode(str: string): string {
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
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
