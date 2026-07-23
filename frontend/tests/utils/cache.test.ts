import { assertEquals, assert } from "https://deno.land/std@0.224.0/assert/mod.ts";

// Importamos createCache desde su ruta interna (la exportación privada)
// Usamos el perfil público: profileCache y latestExecutionCache
import { profileCache } from "../../utils/cache.ts";

Deno.test("cache - profileCache starts with no data", () => {
  assertEquals(profileCache.hasData(), false);
  assertEquals(profileCache.get(), null);
  assertEquals(profileCache.isValid(), false);
});

Deno.test("cache - profileCache set then hasData and get work", () => {
  const user = { username: "test", firstname: "Test", lastname: "User", profileimageurl: "" };
  profileCache.set(user);
  assertEquals(profileCache.hasData(), true);
  assertEquals(profileCache.get()?.username, "test");
  assertEquals(profileCache.get()?.firstname, "Test");
});

Deno.test("cache - profileCache isValid returns true right after set", () => {
  assert(profileCache.isValid());
});
