// tests/services/api.test.ts
import {
  login,
  uploadFile,
  startProcess,
  getExecution,
  listExecutions,
  getExecutionErrors,
  deleteExecution,
  getHistory,
  getSemaphore,
  getLatest,
} from "../../services/api.ts";

import {
  assertEquals,
  assertRejects,
} from "https://deno.land/std@0.224.0/assert/mod.ts";

// ---------------------------------------------------------------------------
// Mock de fetch
// ---------------------------------------------------------------------------
let mockFetchResponse: Response;
let lastFetchArgs: { url?: string; init?: RequestInit } = {};

function createResponse(status: number, body: unknown): Response {
  if (status === 204) {
    return new Response(null, {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(status: number, body: unknown) {
  mockFetchResponse = createResponse(status, body);
}

// deno-lint-ignore require-await
async function fakeFetch(input: RequestInfo | URL, init?: RequestInit) {
  lastFetchArgs = { url: String(input), init };
  return mockFetchResponse;
}

// deno-lint-ignore no-explicit-any
globalThis.fetch = fakeFetch as any;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function setFakeToken(token = "mi-token-jwt") {
  localStorage.setItem("auth_token", token);
}

function setup() {
  lastFetchArgs = {};
  localStorage.clear();
}

// ---------------------------------------------------------------------------
// Pruebas
// ---------------------------------------------------------------------------
Deno.test("api - login exitoso retorna datos del usuario", async () => {
  setup();
  mockFetch(200, { access_token: "jwt123", user_id: 1, username: "juan", modalidad: "PRESENCIAL" });
  const result = await login("juan", "secreto", "PRESENCIAL");
  assertEquals(result.access_token, "jwt123");
  assertEquals(result.user_id, 1);
  const body = JSON.parse(lastFetchArgs.init?.body as string);
  assertEquals(body.username, "juan");
  assertEquals(body.password, "secreto");
  assertEquals(body.modalidad, "PRESENCIAL");
});

Deno.test(
  "api - login fallido lanza error con el detalle del backend (código 400)",
  async () => {
    setup();
    mockFetch(400, { detail: "Credenciales incorrectas" });
    await assertRejects(
      () => login("juan", "mal", "PRESENCIAL"),
      Error,
      "Credenciales incorrectas",
    );
  },
);

Deno.test("api - uploadFile envía el archivo y devuelve ejecución", async () => {
  setup();
  setFakeToken();
  const fakeFile = new File(["dummy content"], "datos.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  mockFetch(201, {
    execution_id: 42,
    filename: "datos.xlsx",
    status: "pending",
  });
  const result = await uploadFile(fakeFile, "2025A", "DISTANCIA");
  assertEquals(result.execution_id, 42);
});

Deno.test(
  "api - uploadFile sin token envía de todas formas (el backend rechazará 403)",
  async () => {
    setup();
    const fakeFile = new File(["x"], "test.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    mockFetch(403, { detail: "No autenticado" });
    await assertRejects(
      () => uploadFile(fakeFile, "2025A", "DISTANCIA"),
      Error,
      "No autenticado",
    );
  },
);

Deno.test("api - startProcess encola una ejecución", async () => {
  setup();
  setFakeToken();
  mockFetch(202, { execution_id: 10, job_id: "rq:job:1" });
  const result = await startProcess(10);
  assertEquals(result.job_id, "rq:job:1");
  assertEquals(lastFetchArgs.url?.includes("/jobs/10/process"), true);
});

Deno.test("api - getExecution retorna el objeto Execution", async () => {
  setup();
  setFakeToken();
  mockFetch(200, {
    id: 5,
    filename: "carga.xlsx",
    semester: "2025A",
    mode: "both",
    status: "completed",
    errors_count: 0,
    created_at: "2025-03-01T10:00:00Z",
  });
  const exec = await getExecution(5);
  assertEquals(exec.id, 5);
  assertEquals(exec.semester, "2025A");
});

Deno.test("api - listExecutions retorna lista paginada con filtros", async () => {
  setup();
  setFakeToken();
  mockFetch(200, { total: 2, items: [{ id: 1 }, { id: 2 }] });
  const result = await listExecutions({
    semester: "2025A",
    limit: 5,
    offset: 0,
  });
  assertEquals(result.total, 2);
  assertEquals(result.items.length, 2);
  assertEquals(lastFetchArgs.url?.includes("semester=2025A"), true);
});

Deno.test("api - getExecutionErrors retorna lista de errores", async () => {
  setup();
  setFakeToken();
  mockFetch(200, [{ id: 1, type: "course", message: "Curso no encontrado" }]);
  const errors = await getExecutionErrors(5, 10, 0);
  assertEquals(errors.length, 1);
  assertEquals(errors[0].type, "course");
});

Deno.test("api - deleteExecution sin error no lanza excepción (204)", async () => {
  setup();
  setFakeToken();
  mockFetch(204, null);
  await deleteExecution(10);
});

Deno.test("api - deleteExecution con error lanza", async () => {
  setup();
  setFakeToken();
  mockFetch(500, { detail: "Error interno" });
  await assertRejects(() => deleteExecution(10), Error, "Error interno");
});

Deno.test("api - getHistory retorna métricas por semestre", async () => {
  setup();
  setFakeToken();
  mockFetch(200, [
    {
      semester: "2025A",
      total_executions: 2,
      total_courses_created: 10,
      total_errors: 1,
    },
  ]);
  const history = await getHistory(5);
  assertEquals(history[0].semester, "2025A");
});

Deno.test("api - getSemaphore retorna estado del semáforo", async () => {
  setup();
  setFakeToken();
  mockFetch(200, { semester: "2025A", status: "green", error_rate: 0.5 });
  const sem = await getSemaphore("2025A");
  assertEquals(sem.status, "green");
  assertEquals(lastFetchArgs.url?.includes("semester=2025A"), true);
});

Deno.test("api - getSemaphore sin parámetro consulta último", async () => {
  setup();
  setFakeToken();
  mockFetch(200, { semester: "2025A", status: "yellow" });
  const sem = await getSemaphore();
  assertEquals(sem.status, "yellow");
});

Deno.test("api - getLatest retorna la última ejecución con semáforo", async () => {
  setup();
  setFakeToken();
  mockFetch(200, {
    id: 99,
    semester: "2024B",
    status: "completed",
    error_rate: 0.0,
    semaphore: "green",
  });
  const latest = await getLatest();
  assertEquals(latest.id, 99);
  assertEquals(latest.semaphore, "green");
});

Deno.test("api - respuesta 401 borra token y redirige al login", async () => {
  setup();
  localStorage.setItem("auth_token", "mi-token-jwt");

  mockFetch(401, { detail: "Token expirado" });
  await assertRejects(
    () => getExecution(1),
    Error,
    "Sesión expirada. Vuelva a iniciar sesión.",
  );
  assertEquals(localStorage.getItem("auth_token"), null);
});

Deno.test("api - error login sin mensaje detalle muestra fallback", async () => {
  setup();
  mockFetch(500, {});
  await assertRejects(
    () => login("juan", "pass", "PRESENCIAL"),
    Error,
    "Credenciales inválidas",
  );
});
