import { assertEquals } from "@std/assert";
import type { CensoObservatorio } from "../../services/api.ts";
import {
  censoEstaVencido,
  claveCat,
  construirIndicesMapaObservatorio,
  esEstadoTerminalConsulta,
  filtrarDepartamentosObservatorio,
  pluralizarConteo,
} from "../../utils/observatorio.ts";

const CENSO_DEMO: CensoObservatorio = {
  total_students: 120,
  total_departments: 1,
  total_municipalities: 1,
  total_cats: 2,
  total_programs: 2,
  total_courses: 4,
  updated_at: "2026-11-24T17:00:00.000Z",
  departments: [
    {
      dpto_code: "11",
      dpto_name: "BOGOTÁ, D.C.",
      cats_count: 2,
      students_count: 120,
      municipalities: [
        {
          mpio_code: "11001",
          mpio_name: "BOGOTÁ, D.C.",
          cat_name: "TUNAL",
          cat_shortname: "TUN",
          display_name: "BOGOTÁ, D.C. (TUNAL)",
          lat: 4.57,
          lon: -74.13,
          programs_count: 1,
          students_count: 70,
          programs: [
            {
              program_code: "0852",
              program_name: "INGENIERÍA DE SISTEMAS",
              students_count: 70,
              courses_count: 2,
            },
          ],
        },
        {
          mpio_code: "11001",
          mpio_name: "BOGOTÁ, D.C.",
          cat_name: "KENNEDY",
          cat_shortname: "KEN",
          display_name: "BOGOTÁ, D.C. (KENNEDY)",
          lat: 4.63,
          lon: -74.15,
          programs_count: 1,
          students_count: 50,
          programs: [
            {
              program_code: "0854",
              program_name: "ADMINISTRACIÓN FINANCIERA",
              students_count: 50,
              courses_count: 2,
            },
          ],
        },
      ],
    },
  ],
};

Deno.test("pluralizarConteo - formatea singular y plural correctamente", () => {
  assertEquals(pluralizarConteo(1, "CAT", "CATs"), "1 CAT");
  assertEquals(pluralizarConteo(3, "CAT", "CATs"), "3 CATs");
  assertEquals(pluralizarConteo(1, "Programa", "Programas"), "1 Programa");
});

Deno.test("construirIndicesMapaObservatorio - agrupa múltiples CATs de un mismo municipio", () => {
  const { departamentosPorCodigo, resumenMunicipiosMapa } =
    construirIndicesMapaObservatorio(CENSO_DEMO);
  assertEquals(departamentosPorCodigo.get("11")?.cats_count, 2);
  assertEquals(resumenMunicipiosMapa.length, 1);
  const bog = resumenMunicipiosMapa[0];
  assertEquals(bog.mpioCode, "11001");
  assertEquals(bog.dptoCode, "11");
  assertEquals(bog.totalProgs, 2);
  assertEquals(bog.totalEst, 120);
  assertEquals(bog.clavesCat, ["11001:TUN", "11001:KEN"]);
});

Deno.test("filtrarDepartamentosObservatorio - filtra por programa o CAT y sincroniza contadores", () => {
  const porProg = filtrarDepartamentosObservatorio(
    CENSO_DEMO.departments,
    "0854",
  );
  assertEquals(porProg.length, 1);
  assertEquals(porProg[0].cats_count, 1);
  assertEquals(porProg[0].municipalities.length, 1);
  assertEquals(porProg[0].municipalities[0].cat_shortname, "KEN");
  assertEquals(porProg[0].municipalities[0].programs_count, 1);
  assertEquals(
    claveCat(porProg[0].municipalities[0]),
    "11001:KEN",
  );

  const vacio = filtrarDepartamentosObservatorio(
    CENSO_DEMO.departments,
    "inexistente",
  );
  assertEquals(vacio.length, 0);
});

Deno.test("esEstadoTerminalConsulta - reconoce estados finales de tarea", () => {
  assertEquals(esEstadoTerminalConsulta("completed"), true);
  assertEquals(esEstadoTerminalConsulta("failed"), true);
  assertEquals(esEstadoTerminalConsulta("cancelled"), true);
  assertEquals(esEstadoTerminalConsulta("empty"), true);
  assertEquals(esEstadoTerminalConsulta("running"), false);
  assertEquals(esEstadoTerminalConsulta("pending"), false);
});

Deno.test("censoEstaVencido - detecta antigüedad mayor al umbral", () => {
  const ahora = Date.parse("2026-11-24T18:00:00.000Z");
  assertEquals(
    censoEstaVencido("2026-11-24T17:45:00.000Z", 30 * 60 * 1000, ahora),
    false,
  );
  assertEquals(
    censoEstaVencido("2026-11-24T17:00:00.000Z", 30 * 60 * 1000, ahora),
    true,
  );
  assertEquals(censoEstaVencido(null, 30 * 60 * 1000, ahora), true);
});
