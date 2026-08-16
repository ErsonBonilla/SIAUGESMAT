import { useComputed, useSignal } from "@preact/signals";
import {
  descargarReporte,
  obtenerUrlExportarConsulta,
} from "../services/api.ts";
import { useConsultaTarea } from "../hooks/useConsultaTarea.ts";
import { IconoDescargar, IconoSpinner } from "../utils/iconos.tsx";
import CajaError from "../components/CajaError.tsx";
import Paginacion from "../components/Paginacion.tsx";
import SelectorSemestre from "../components/SelectorSemestre.tsx";
import AyudaConsulta, {
  type SeccionAyudaConsulta,
} from "../components/AyudaConsulta.tsx";

const PAGE_SIZE = 20;

type ModoCorte = "days" | "months" | "years" | "semester";

export interface ColumnaInactivo {
  key: string;
  label: string;
  destacar?: boolean;
  truncar?: boolean;
  render: (row: Record<string, unknown>) => string;
}

interface PropsConsultaInactivos {
  entity: string;
  sustantivo: string;
  columnas: ColumnaInactivo[];
  seccionesAyuda: SeccionAyudaConsulta[];
  nombreCsv: string;
  textoVacio: string;
}

export default function ConsultaInactivos(
  {
    entity,
    sustantivo,
    columnas,
    seccionesAyuda,
    nombreCsv,
    textoVacio,
  }: PropsConsultaInactivos,
) {
  const cutoffMode = useSignal<ModoCorte>("days");
  const semester = useSignal("");
  const days = useSignal(15);
  const months = useSignal(1);
  const years = useSignal(1);
  const { data, loading, error, taskId, taskStatus, iniciarConsulta } =
    useConsultaTarea<Record<string, unknown>>();
  const pageOffset = useSignal(0);
  const totalItems = useComputed(() => data.value.length);
  const pageData = useComputed(() =>
    data.value.slice(pageOffset.value, pageOffset.value + PAGE_SIZE)
  );

  const startQuery = async () => {
    const params: Record<string, string> = {};
    if (cutoffMode.value === "days") {
      const d = Number(days.value);
      if (!Number.isInteger(d) || d < 1 || d > 30) {
        error.value = "Ingrese un número de días válido (1–30).";
        return;
      }
      params.days = String(d);
    } else if (cutoffMode.value === "months") {
      const m = Number(months.value);
      if (!Number.isInteger(m) || m < 1 || m > 12) {
        error.value = "Ingrese un número de meses válido (1–12).";
        return;
      }
      params.months = String(m);
    } else if (cutoffMode.value === "years") {
      const y = Number(years.value);
      if (!Number.isInteger(y) || y < 1) {
        error.value = "Ingrese un número de años válido (≥ 1).";
        return;
      }
      params.years = String(y);
    } else {
      if (!semester.value) {
        error.value = "Seleccione un semestre.";
        return;
      }
      params.semester = semester.value;
    }
    pageOffset.value = 0;
    await iniciarConsulta(entity, params);
  };

  const exportUrl = taskId.value
    ? obtenerUrlExportarConsulta(taskId.value)
    : "";

  return (
    <div class="space-y-4">
      <AyudaConsulta sections={seccionesAyuda} />
      <div class="flex flex-col sm:flex-row sm:items-end gap-4">
        <div class="flex flex-col gap-2">
          <div class="flex gap-1 bg-[var(--bg-tertiary)] rounded-lg p-1 w-fit flex-wrap">
            {(["days", "months", "years", "semester"] as const).map((mode) => {
              const labels: Record<ModoCorte, string> = {
                days: "Por días",
                months: "Por meses",
                years: "Por años",
                semester: "Por semestre",
              };
              return (
                <button
                  type="button"
                  key={mode}
                  onClick={() => cutoffMode.value = mode}
                  class={`px-3 py-1 rounded-md text-sm font-medium transition ${
                    cutoffMode.value === mode
                      ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {labels[mode]}
                </button>
              );
            })}
          </div>
          {cutoffMode.value === "days" && (
            <div>
              <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Días {sustantivo} (mínimo)
              </label>
              <input
                type="number"
                min={1}
                max={30}
                value={days.value}
                onChange={(e) => {
                  days.value = Number(e.currentTarget.value);
                  error.value = "";
                }}
                class="px-3 py-2 border rounded-md w-32 bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
          )}
          {cutoffMode.value === "months" && (
            <div>
              <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Meses {sustantivo} (mínimo)
              </label>
              <input
                type="number"
                min={1}
                max={12}
                value={months.value}
                onChange={(e) => {
                  months.value = Number(e.currentTarget.value);
                  error.value = "";
                }}
                class="px-3 py-2 border rounded-md w-32 bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
          )}
          {cutoffMode.value === "years" && (
            <div>
              <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Años {sustantivo} (mínimo)
              </label>
              <input
                type="number"
                min={1}
                value={years.value}
                onChange={(e) => {
                  years.value = Number(e.currentTarget.value);
                  error.value = "";
                }}
                class="px-3 py-2 border rounded-md w-32 bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
          )}
          {cutoffMode.value === "semester" && (
            <div>
              <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Semestre de corte
              </label>
              <SelectorSemestre
                value={semester.value}
                onChange={(s) => {
                  semester.value = s;
                  error.value = "";
                }}
                anioMinimo={2020}
              />
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={startQuery}
          disabled={loading.value ||
            (cutoffMode.value === "days" &&
              (!Number.isInteger(days.value) || days.value < 1 ||
                days.value > 30)) ||
            (cutoffMode.value === "months" &&
              (!Number.isInteger(months.value) || months.value < 1 ||
                months.value > 12)) ||
            (cutoffMode.value === "years" &&
              (!Number.isInteger(years.value) || years.value < 1)) ||
            (cutoffMode.value === "semester" && !semester.value)}
          class="px-3 py-1.5 bg-[var(--brand-green)] text-white rounded text-sm hover:brightness-90 disabled:opacity-60 self-start mt-6"
        >
          {loading.value
            ? (
              <span class="flex items-center gap-1.5">
                <IconoSpinner class="animate-spin h-4 w-4" />
                Consultando...
              </span>
            )
            : "Consultar"}
        </button>
      </div>

      {loading.value && taskStatus.value?.status === "running" && (
        <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <IconoSpinner class="animate-spin h-4 w-4" />
          <span>
            Consultando Moodle (procesando {taskStatus.value?.total_count || 0}
            {" "}
            cursos)... puede tardar varios minutos.
          </span>
        </div>
      )}

      {error.value && <CajaError message={error.value} />}

      {!loading.value && !error.value && data.value.length > 0 && (
        <div class="flex items-center justify-between">
          <span class="text-xs text-[var(--text-secondary)]">
            {pageOffset.value + 1}–{Math.min(
              pageOffset.value + PAGE_SIZE,
              totalItems.value,
            )} de {totalItems.value}{" "}
            resultado{totalItems.value !== 1 ? "s" : ""}
          </span>
          {exportUrl && (
            <button
              type="button"
              onClick={() =>
                descargarReporte(exportUrl, nombreCsv).catch(() => {})}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-tertiary)] text-[var(--text-primary)] rounded text-sm font-medium no-underline hover:bg-[var(--border-secondary)] transition cursor-pointer"
            >
              <IconoDescargar class="w-4 h-4" />
              CSV
            </button>
          )}
        </div>
      )}

      {!loading.value && !error.value && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border-primary)]">
                {columnas.map((col) => (
                  <th
                    key={col.key}
                    class="text-left py-3 px-3 font-medium text-[var(--text-secondary)]"
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.value.length === 0 && !loading.value
                ? (
                  <tr>
                    <td
                      colSpan={columnas.length}
                      class="py-12 text-center text-[var(--text-muted)]"
                    >
                      {textoVacio}
                    </td>
                  </tr>
                )
                : pageData.value.map((row, idx) => (
                  <tr
                    key={idx}
                    class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
                  >
                    {columnas.map((col) => (
                      <td
                        key={col.key}
                        class={`py-2 px-3 text-[var(--text-primary)] ${
                          col.destacar ? "font-medium" : ""
                        } ${col.truncar ? "max-w-xs truncate" : ""}`}
                        title={col.truncar ? col.render(row) : undefined}
                      >
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading.value && !error.value && data.value.length > PAGE_SIZE && (
        <Paginacion
          offset={pageOffset.value}
          tamanoPagina={PAGE_SIZE}
          total={totalItems.value}
          label="resultados"
          alCambiarPagina={(o) => {
            pageOffset.value = o;
          }}
        />
      )}
    </div>
  );
}
