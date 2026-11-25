import { useComputed, useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import Disposicion from "../components/Disposicion.tsx";
import Tarjeta from "../components/Tarjeta.tsx";
import EsqueletoCarga from "../components/EsqueletoCarga.tsx";
import CajaError from "../components/CajaError.tsx";
import MapaColombiaSvg, {
  type DatosMapaColombia,
} from "../components/MapaColombiaSvg.tsx";
import ArbolObservatorio from "../components/ArbolObservatorio.tsx";
import {
  type CensoObservatorio,
  consultarEntidades,
  obtenerEstadoTareaConsulta,
  obtenerUltimoObservatorio,
} from "../services/api.ts";
import { tiempoRelativo } from "../utils/fechas.ts";
import { IconoRecargar, IconoSpinner } from "../utils/iconos.tsx";
import {
  censoEstaVencido,
  claveCat,
  construirIndicesMapaObservatorio,
  esEstadoTerminalConsulta,
} from "../utils/observatorio.ts";

const AUTO_REFRESH_AGE_MS = 30 * 60 * 1000;
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 300;

function TarjetaResumenObservatorio({
  datos,
  sincronizando,
  onSincronizar,
}: {
  datos: CensoObservatorio | null;
  sincronizando: boolean;
  onSincronizar: () => void;
}) {
  const subtitulo = datos?.updated_at
    ? `Actualizado ${tiempoRelativo(datos.updated_at)}`
    : sincronizando
    ? "Consultando cursos visibles con docente en Moodle…"
    : "Sin censo previo";

  return (
    <Tarjeta padding="md">
      <div class="flex items-start justify-between gap-3 mb-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            Estudiantes Matriculados (Cursos Activos IDEAD)
          </p>
          <p class="text-3xl font-extrabold text-[var(--text-primary)] mt-1">
            {datos ? datos.total_students.toLocaleString() : "—"}
          </p>
          <p class="text-xs text-[var(--text-secondary)] mt-1">{subtitulo}</p>
        </div>

        <button
          type="button"
          onClick={onSincronizar}
          disabled={sincronizando}
          aria-busy={sincronizando}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--border-secondary)] bg-[var(--bg-secondary)] text-[var(--text-primary)] hover:border-[var(--accent)] cursor-pointer disabled:opacity-60 transition"
        >
          {sincronizando
            ? (
              <>
                <IconoSpinner class="w-3.5 h-3.5 animate-spin" />
                <span>Sincronizando…</span>
              </>
            )
            : (
              <>
                <IconoRecargar class="w-3.5 h-3.5" />
                <span>Actualizar</span>
              </>
            )}
        </button>
      </div>

      <div class="grid grid-cols-3 gap-2.5 pt-3 border-t border-[var(--border-primary)] text-center">
        <div class="p-2 rounded-lg bg-[var(--bg-secondary)]">
          <span class="text-lg font-bold block" style={{ color: "#ED3237" }}>
            {datos ? datos.total_departments : "—"}
          </span>
          <span class="text-[0.6875rem] text-[var(--text-secondary)]">
            Departamentos
          </span>
        </div>
        <div class="p-2 rounded-lg bg-[var(--bg-secondary)]">
          <span class="text-lg font-bold block" style={{ color: "#00A859" }}>
            {datos ? datos.total_cats : "—"}
          </span>
          <span class="text-[0.6875rem] text-[var(--text-secondary)]">
            CATs Activos
          </span>
        </div>
        <div class="p-2 rounded-lg bg-[var(--bg-secondary)]">
          <span class="text-lg font-bold text-[var(--text-primary)] block">
            {datos ? datos.total_programs : "—"}
          </span>
          <span class="text-[0.6875rem] text-[var(--text-secondary)]">
            Programas
          </span>
        </div>
      </div>
    </Tarjeta>
  );
}

export default function IslandPanel() {
  const mapa = useSignal<DatosMapaColombia | null>(null);
  const censo = useSignal<CensoObservatorio | null>(null);
  const cargandoInicial = useSignal(true);
  const sincronizando = useSignal(false);
  const idTareaActiva = useSignal<string | null>(null);
  const error = useSignal("");

  const busqueda = useSignal("");
  const tooltipMapa = useSignal("");
  const dptoSeleccionado = useSignal<string | null>(null);
  const mpioSeleccionado = useSignal<string | null>(null);
  const dptosAbiertos = useSignal<Set<string>>(new Set());
  const catsAbiertos = useSignal<Set<string>>(new Set());

  const iniciarSincronizacion = async () => {
    if (sincronizando.value) return;
    sincronizando.value = true;
    error.value = "";
    try {
      const resp = await consultarEntidades("observatorio");
      idTareaActiva.value = resp.task_id;
    } catch (e) {
      sincronizando.value = false;
      error.value = e instanceof Error
        ? e.message
        : "No se pudo iniciar la sincronización con Moodle.";
    }
  };

  useEffect(() => {
    let cancelado = false;
    cargandoInicial.value = true;

    Promise.allSettled([
      fetch("/mapa/colombia_mapa.json").then((r) => {
        if (!r.ok) throw new Error("No se pudo cargar la cartografía DANE.");
        return r.json() as Promise<DatosMapaColombia>;
      }),
      obtenerUltimoObservatorio(),
    ])
      .then(([resMapa, resUltimo]) => {
        if (cancelado) return;

        if (resMapa.status === "fulfilled") {
          mapa.value = resMapa.value;
        } else {
          error.value = "No se pudo cargar la cartografía del mapa.";
        }

        const ultimo = resUltimo.status === "fulfilled"
          ? resUltimo.value
          : null;

        if (ultimo?.result) {
          censo.value = ultimo.result;
          const primero = ultimo.result.departments[0];
          if (primero) dptosAbiertos.value = new Set([primero.dpto_code]);
        }

        if (ultimo?.active_task_id) {
          sincronizando.value = true;
          idTareaActiva.value = ultimo.active_task_id;
          return;
        }

        if (censoEstaVencido(ultimo?.updated_at, AUTO_REFRESH_AGE_MS)) {
          iniciarSincronizacion();
        }
      })
      .finally(() => {
        if (!cancelado) cargandoInicial.value = false;
      });

    return () => {
      cancelado = true;
    };
  }, []);

  useEffect(() => {
    const taskId = idTareaActiva.value;
    if (!taskId) return;

    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelado = false;
    let intentos = 0;

    const detenerPolling = (mensajeError = "") => {
      sincronizando.value = false;
      idTareaActiva.value = null;
      if (mensajeError) error.value = mensajeError;
    };

    const verificar = async () => {
      intentos += 1;
      if (intentos > MAX_POLL_ATTEMPTS) {
        detenerPolling(
          "La sincronización con Moodle excedió el tiempo de espera.",
        );
        return;
      }

      try {
        const st = await obtenerEstadoTareaConsulta<CensoObservatorio>(taskId);
        if (cancelado) return;

        if (st.status === "completed") {
          if (st.result) {
            censo.value = st.result;
            error.value = "";
            if (dptosAbiertos.value.size === 0 && st.result.departments[0]) {
              dptosAbiertos.value = new Set([
                st.result.departments[0].dpto_code,
              ]);
            }
          }
          detenerPolling();
          return;
        }

        if (esEstadoTerminalConsulta(st.status)) {
          detenerPolling(st.error || "La consulta del Observatorio finalizó.");
          return;
        }

        timer = setTimeout(verificar, POLL_INTERVAL_MS);
      } catch (e) {
        if (!cancelado) {
          detenerPolling(
            e instanceof Error
              ? e.message
              : "Error consultando estado del Observatorio.",
          );
        }
      }
    };

    timer = setTimeout(verificar, POLL_INTERVAL_MS);
    return () => {
      cancelado = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [idTareaActiva.value]);

  const indicesMapa = useComputed(() =>
    construirIndicesMapaObservatorio(censo.value)
  );

  const toggleDpto = (dptoCode: string) => {
    const copia = new Set(dptosAbiertos.value);
    const abriendo = !copia.has(dptoCode);
    if (abriendo) {
      copia.add(dptoCode);
      dptoSeleccionado.value = dptoCode;
    } else {
      copia.delete(dptoCode);
      if (dptoSeleccionado.value === dptoCode) {
        dptoSeleccionado.value = null;
        mpioSeleccionado.value = null;
      }
    }
    dptosAbiertos.value = copia;
  };

  const toggleCat = (clave: string, dptoCode: string, mpioCode: string) => {
    const copia = new Set(catsAbiertos.value);
    const abriendo = !copia.has(clave);
    if (abriendo) {
      copia.add(clave);
      dptoSeleccionado.value = dptoCode;
      mpioSeleccionado.value = mpioCode;
    } else {
      copia.delete(clave);
      if (mpioSeleccionado.value === mpioCode) {
        mpioSeleccionado.value = null;
      }
    }
    catsAbiertos.value = copia;
  };

  const seleccionarDptoDesdeMapa = (dptoCode: string) => {
    const copia = new Set(dptosAbiertos.value);
    copia.add(dptoCode);
    dptosAbiertos.value = copia;
    dptoSeleccionado.value = dptoCode;
    mpioSeleccionado.value = null;
  };

  const seleccionarMpioDesdeMapa = (dptoCode: string, mpioCode: string) => {
    const copiaDptos = new Set(dptosAbiertos.value);
    copiaDptos.add(dptoCode);
    dptosAbiertos.value = copiaDptos;

    const copiaCats = new Set(catsAbiertos.value);
    const resumen = indicesMapa.value.resumenMunicipiosMapa.find(
      (r) => r.mpioCode === mpioCode,
    );
    for (const c of resumen?.clavesCat ?? []) {
      copiaCats.add(c);
    }
    catsAbiertos.value = copiaCats;
    dptoSeleccionado.value = dptoCode;
    mpioSeleccionado.value = mpioCode;
  };

  const expandirTodo = () => {
    const dptos = new Set<string>();
    const cats = new Set<string>();
    for (const d of censo.value?.departments ?? []) {
      dptos.add(d.dpto_code);
      for (const m of d.municipalities) {
        cats.add(claveCat(m));
      }
    }
    dptosAbiertos.value = dptos;
    catsAbiertos.value = cats;
  };

  const colapsarTodo = () => {
    dptosAbiertos.value = new Set();
    catsAbiertos.value = new Set();
    dptoSeleccionado.value = null;
    mpioSeleccionado.value = null;
  };

  return (
    <Disposicion title="Observatorio IDEAD Colombia">
      <div class="space-y-5">
        {error.value && <CajaError message={error.value} />}

        {cargandoInicial.value && !mapa.value
          ? (
            <div class="space-y-4">
              <EsqueletoCarga variant="kpi" />
              <EsqueletoCarga variant="chart" />
            </div>
          )
          : (
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              <div class="lg:col-span-7">
                <Tarjeta padding="md">
                  {mapa.value && (
                    <MapaColombiaSvg
                      mapa={mapa.value}
                      departamentosPorCodigo={indicesMapa.value
                        .departamentosPorCodigo}
                      resumenMunicipiosMapa={indicesMapa.value
                        .resumenMunicipiosMapa}
                      dptoSeleccionado={dptoSeleccionado.value}
                      mpioSeleccionado={mpioSeleccionado.value}
                      tooltipTexto={tooltipMapa.value}
                      onHoverTexto={(t) => (tooltipMapa.value = t)}
                      onSeleccionarDpto={seleccionarDptoDesdeMapa}
                      onSeleccionarMpio={seleccionarMpioDesdeMapa}
                    />
                  )}
                </Tarjeta>
              </div>

              <div class="lg:col-span-5 flex flex-col gap-4">
                <TarjetaResumenObservatorio
                  datos={censo.value}
                  sincronizando={sincronizando.value}
                  onSincronizar={iniciarSincronizacion}
                />

                <Tarjeta padding="md">
                  <div class="mb-3">
                    <input
                      type="text"
                      aria-label="Filtrar departamento, municipio (CAT) o programa"
                      value={busqueda.value}
                      onInput={(
                        e,
                      ) => (busqueda.value =
                        (e.target as HTMLInputElement).value)}
                      placeholder="Filtrar departamento, municipio (CAT) o programa…"
                      class="w-full px-3 py-2 rounded-lg text-sm border border-[var(--border-secondary)] bg-[var(--bg-secondary)] text-[var(--text-primary)]"
                    />
                  </div>

                  {!censo.value && sincronizando.value
                    ? (
                      <div class="py-10 flex flex-col items-center justify-center gap-3 text-sm text-[var(--text-secondary)]">
                        <IconoSpinner class="w-6 h-6 animate-spin text-[var(--brand-green)]" />
                        <span>
                          Construyendo censo del Observatorio desde Moodle…
                        </span>
                      </div>
                    )
                    : (
                      <ArbolObservatorio
                        departamentos={censo.value?.departments ?? []}
                        dptosAbiertos={dptosAbiertos.value}
                        catsAbiertos={catsAbiertos.value}
                        busqueda={busqueda.value}
                        onToggleDpto={toggleDpto}
                        onToggleCat={toggleCat}
                        onExpandirTodo={expandirTodo}
                        onColapsarTodo={colapsarTodo}
                      />
                    )}
                </Tarjeta>
              </div>
            </div>
          )}
      </div>
    </Disposicion>
  );
}
