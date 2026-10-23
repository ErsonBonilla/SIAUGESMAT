import { tokenHaExpirado } from "../../utils/autenticacion.ts";
import { assert, assertFalse } from "@std/assert";

function base64urlEncode(str: string): string {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function makeToken(payload: Record<string, unknown>): string {
  const header = base64urlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  return `${header}.${base64urlEncode(JSON.stringify(payload))}.fakesignature`;
}

Deno.test("tokenHaExpirado - false con token no expirado", () => {
  const token = makeToken({ exp: Math.floor(Date.now() / 1000) + 3600 });
  assertFalse(tokenHaExpirado(token));
});

Deno.test("tokenHaExpirado - true con token expirado", () => {
  const token = makeToken({ exp: Math.floor(Date.now() / 1000) - 60 });
  assert(tokenHaExpirado(token));
});

Deno.test("tokenHaExpirado - false si no hay campo exp", () => {
  const token = makeToken({ username: "test" });
  assertFalse(tokenHaExpirado(token));
});

Deno.test("tokenHaExpirado - true con token malformado", () => {
  assert(tokenHaExpirado("no-es-un-jwt"));
  assert(tokenHaExpirado(""));
});

Deno.test("tokenHaExpirado - decodifica base64url con UTF-8 sin lanzar", () => {
  // El payload contiene caracteres no ASCII; la decodificación UTF-8 debe
  // funcionar y devolver el exp correcto.
  const token = makeToken({
    username: "profe/paño",
    exp: Math.floor(Date.now() / 1000) + 3600,
  });
  assertFalse(tokenHaExpirado(token));
});
