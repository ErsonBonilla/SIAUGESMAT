import type {
  CensoObservatorio,
  DepartamentoObservatorio,
  MunicipioCatObservatorio,
} from "../services/api.ts";

const ESTADOS_TERMINALES_CONSULTA = new Set([
  "completed",
  "failed",
  "cancelled",
  "empty",
]);

export interface ResumenMunicipioMapa {
  mpioCode: string;
  dptoCode: string;
  totalProgs: number;
  totalEst: number;
  etiquetaTooltip: string;
  clavesCat: string[];
}

export interface IndicesMapaObservatorio {
  departamentosPorCodigo: Map<string, DepartamentoObservatorio>;
  resumenMunicipiosMapa: ResumenMunicipioMapa[];
}

export function claveCat(
  mpio: Pick<MunicipioCatObservatorio, "mpio_code" | "cat_shortname">,
): string {
  return `${mpio.mpio_code}:${mpio.cat_shortname}`;
}

export function esEstadoTerminalConsulta(status: string): boolean {
  return ESTADOS_TERMINALES_CONSULTA.has(status);
}

export function pluralizarConteo(
  cantidad: number,
  singular: string,
  plural: string,
): string {
  const num = Number.isFinite(cantidad) ? cantidad : 0;
  return `${num.toLocaleString()} ${num === 1 ? singular : plural}`;
}

export function censoEstaVencido(
  updatedAt: string | null | undefined,
  maxAgeMs: number,
  ahoraMs = Date.now(),
): boolean {
  if (!updatedAt) return true;
  const ts = Date.parse(updatedAt);
  if (Number.isNaN(ts)) return true;
  return ahoraMs - ts >= maxAgeMs;
}

function resumirMunicipio(
  mpioCode: string,
  dptoCode: string,
  sedes: MunicipioCatObservatorio[],
): ResumenMunicipioMapa {
  let totalProgs = 0;
  let totalEst = 0;
  const nombres: string[] = [];
  const clavesCat: string[] = [];

  for (const s of sedes) {
    totalProgs += s.programs_count;
    totalEst += s.students_count;
    nombres.push(s.display_name);
    clavesCat.push(claveCat(s));
  }

  const etiquetaTooltip = `${nombres.join(" / ")}: ${
    pluralizarConteo(totalProgs, "Programa", "Programas")
  } · ${pluralizarConteo(totalEst, "estudiante", "estudiantes")}`;

  return {
    mpioCode,
    dptoCode,
    totalProgs,
    totalEst,
    etiquetaTooltip,
    clavesCat,
  };
}

export function construirIndicesMapaObservatorio(
  censo: CensoObservatorio | null,
): IndicesMapaObservatorio {
  const departamentosPorCodigo = new Map<string, DepartamentoObservatorio>();
  const sedesPorMpio = new Map<
    string,
    { dptoCode: string; sedes: MunicipioCatObservatorio[] }
  >();

  for (const d of censo?.departments ?? []) {
    departamentosPorCodigo.set(d.dpto_code, d);
    for (const m of d.municipalities) {
      const actual = sedesPorMpio.get(m.mpio_code) ?? {
        dptoCode: d.dpto_code,
        sedes: [],
      };
      actual.sedes.push(m);
      sedesPorMpio.set(m.mpio_code, actual);
    }
  }

  const resumenMunicipiosMapa: ResumenMunicipioMapa[] = [];
  for (const [mCode, { dptoCode, sedes }] of sedesPorMpio.entries()) {
    resumenMunicipiosMapa.push(resumirMunicipio(mCode, dptoCode, sedes));
  }

  return { departamentosPorCodigo, resumenMunicipiosMapa };
}

function filtrarMunicipioPorTexto(
  mpio: MunicipioCatObservatorio,
  filtro: string,
): MunicipioCatObservatorio | null {
  if (
    mpio.display_name.toLowerCase().includes(filtro) ||
    mpio.mpio_name.toLowerCase().includes(filtro) ||
    mpio.cat_shortname.toLowerCase().includes(filtro)
  ) {
    return mpio;
  }
  const programs = mpio.programs.filter(
    (p) =>
      p.program_name.toLowerCase().includes(filtro) ||
      p.program_code.toLowerCase().includes(filtro),
  );
  return programs.length > 0
    ? { ...mpio, programs_count: programs.length, programs }
    : null;
}

export function filtrarDepartamentosObservatorio(
  departamentos: DepartamentoObservatorio[],
  busqueda: string,
): DepartamentoObservatorio[] {
  const filtro = busqueda.trim().toLowerCase();
  if (!filtro) return departamentos;

  const resultado: DepartamentoObservatorio[] = [];
  for (const dpto of departamentos) {
    if (dpto.dpto_name.toLowerCase().includes(filtro)) {
      resultado.push(dpto);
      continue;
    }
    const municipalities: MunicipioCatObservatorio[] = [];
    for (const m of dpto.municipalities) {
      const filtrado = filtrarMunicipioPorTexto(m, filtro);
      if (filtrado) municipalities.push(filtrado);
    }
    if (municipalities.length > 0) {
      resultado.push({
        ...dpto,
        cats_count: municipalities.length,
        municipalities,
      });
    }
  }
  return resultado;
}
