import { assertEquals } from "@std/assert";
import { leerTokenCsrf } from "../../utils/csrf.ts";

function conDocumentoCookie(cookie: string, fn: () => void) {
  const original = (globalThis as unknown as { document?: unknown }).document;
  (globalThis as unknown as { document: unknown }).document = { cookie };
  try {
    fn();
  } finally {
    if (original === undefined) {
      delete (globalThis as unknown as { document?: unknown }).document;
    } else {
      (globalThis as unknown as { document: unknown }).document = original;
    }
  }
}

Deno.test("leerTokenCsrf - vacío sin document", () => {
  assertEquals(leerTokenCsrf(), "");
});

Deno.test("leerTokenCsrf - lee la cookie csrf_token", () => {
  conDocumentoCookie("theme=dark; csrf_token=abc123; other=x", () => {
    assertEquals(leerTokenCsrf(), "abc123");
  });
});

Deno.test("leerTokenCsrf - vacío si no está la cookie", () => {
  conDocumentoCookie("theme=dark; other=x", () => {
    assertEquals(leerTokenCsrf(), "");
  });
});
