import { useComputed, useSignal } from "@preact/signals";
import {
  descargarReporte,
  obtenerUrlExportarConsulta,
} from "../services/api.ts";
import { useConsultaTarea } from "../hooks/useConsultaTarea.ts";
import { IconoDescargar, IconoSpinner } from "../utils/iconos.tsx";
import CajaError from "../components/CajaError.tsx";
import Paginacion from "../components/Paginacion.tsx";
import AyudaConsulta, {
  type SeccionAyudaConsulta,
} from "../components/AyudaConsulta.tsx";

const PAGE_SIZE = 20;

export interface Columna {
  key: string;
  label: string;
  renderKey?: string;
}

const RENDERERS: Record<
  string,
  (value: unknown, row: Record<string, unknown>) => string
> = {
  yesNo: (v) => v == 1 ? "Sí" : "No",
  lastlogin: (v) =>
    typeof v === "number" && v > 0
      ? new Date(v * 1000).toLocaleString()
      : "Nunca",
};

export interface Filtro {
  key: string;
  label: string;
  type: "select" | "checkbox";
  options?: { value: string; label: string }[];
}

interface PropsTablaConsulta {
  entity: string;
  columns: Columna[];
  filters?: Filtro[];
  searchPlaceholder?: string;
  searchKey?: string;
  help?: SeccionAyudaConsulta[];
}

export default function TablaConsulta(
  {
    entity,
    columns,
    filters,
    searchPlaceholder,
    searchKey = "search",
    help,
  }: PropsTablaConsulta,
) {
  const { data, loading, error, taskId, taskStatus, iniciarConsulta } =
    useConsultaTarea<Record<string, unknown>>();
  const search = useSignal("");
  const filterValues = useSignal<Record<string, string>>({});
  const pageOffset = useSignal(0);
  const totalItems = useComputed(() => data.value.length);
  const pageData = useComputed(() =>
    data.value.slice(pageOffset.value, pageOffset.value + PAGE_SIZE)
  );

  const startQuery = async () => {
    pageOffset.value = 0;
    const params: Record<string, string> = {};
    for (const [k, v] of Object.entries(filterValues.value)) {
      if (v && v !== "false") {
        params[k] = v;
      }
    }
    if (search.value.trim()) {
      params[searchKey] = search.value.trim();
    }
    await iniciarConsulta(entity, params);
  };

  const handleSearch = (e: Event) => {
    e.preventDefault();
    startQuery();
  };

  const handleFilterChange = (key: string, value: string) => {
    filterValues.value = { ...filterValues.value, [key]: value };
  };

  const handlePageChange = (offset: number) => {
    pageOffset.value = offset;
  };

  const exportUrl = taskId.value
    ? obtenerUrlExportarConsulta(taskId.value)
    : "";

  return (
    <div>
      {help && help.length > 0 && <AyudaConsulta sections={help} />}
      <div class="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
        {filters?.map((f) =>
          f.type === "checkbox"
            ? (
              <label
                key={f.key}
                class="flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={filterValues.value[f.key] === "true"}
                  onChange={(e) =>
                    handleFilterChange(
                      f.key,
                      (e.target as HTMLInputElement).checked ? "true" : "false",
                    )}
                  class="h-4 w-4 accent-[var(--brand-green)]"
                />
                {f.label}
              </label>
            )
            : (
              <select
                key={f.key}
                value={filterValues.value[f.key] || f.options![0].value}
                onChange={(e) =>
                  handleFilterChange(
                    f.key,
                    (e.target as HTMLSelectElement).value,
                  )}
                class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
              >
                {f.options!.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            )
        )}

        {searchPlaceholder && (
          <form onSubmit={handleSearch} class="flex gap-2">
            <input
              type="text"
              value={search.value}
              onInput={(
                e,
              ) => (search.value = (e.target as HTMLInputElement).value)}
              placeholder={searchPlaceholder}
              class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)] w-48"
            />
            <button
              type="submit"
              class="px-3 py-1.5 bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white rounded text-sm hover:brightness-110"
            >
              Buscar
            </button>
          </form>
        )}

        <button
          type="button"
          onClick={startQuery}
          disabled={loading.value}
          class="px-3 py-1.5 bg-[var(--brand-green)] text-white rounded text-sm hover:brightness-90 disabled:opacity-60"
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

        {exportUrl && data.value.length > 0 && (
          <button
            type="button"
            onClick={() => {
              descargarReporte(exportUrl, "consulta.csv").catch(() => {});
            }}
            class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-tertiary)] text-[var(--text-primary)] rounded text-sm font-medium no-underline hover:bg-[var(--border-secondary)] transition ml-auto cursor-pointer"
          >
            <IconoDescargar class="w-4 h-4" />
            CSV
          </button>
        )}
      </div>

      {loading.value && taskStatus.value?.status === "running" && (
        <div class="flex flex-col gap-2 mb-4">
          <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <IconoSpinner class="animate-spin h-4 w-4" />
            <span>Consultando Moodle... (puede tardar hasta 5 minutos)</span>
          </div>
          {taskStatus.value?.total_count > 0 && (
            <div class="text-xs text-[var(--text-secondary)]">
              {taskStatus.value.total_count}{" "}
              resultados encontrados hasta ahora...
            </div>
          )}
        </div>
      )}

      {error.value && (
        <div class="mb-4">
          <CajaError message={error.value} />
        </div>
      )}

      {!loading.value && !error.value && data.value.length > 0 && (
        <div class="text-xs text-[var(--text-secondary)] mb-2">
          {pageOffset.value + 1}–{Math.min(
            pageOffset.value + PAGE_SIZE,
            totalItems.value,
          )} de {totalItems.value} resultado{totalItems.value !== 1 ? "s" : ""}
        </div>
      )}

      {!loading.value && !error.value && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border-primary)]">
                {columns.map((col) => (
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
                      colSpan={columns.length}
                      class="py-12 text-center text-[var(--text-muted)]"
                    >
                      Sin resultados. Usá los filtros y presioná "Consultar".
                    </td>
                  </tr>
                )
                : pageData.value.map((row, idx) => (
                  <tr
                    key={idx}
                    class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        class="py-2 px-3 text-[var(--text-primary)]"
                      >
                        {col.renderKey
                          ? RENDERERS[col.renderKey](row[col.key], row)
                          : String(row[col.key] ?? "—")}
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
          alCambiarPagina={handlePageChange}
        />
      )}

      {!loading.value && !error.value && data.value.length === 0 &&
        taskStatus.value?.status === "completed" && (
        <div class="text-center py-12 text-[var(--text-muted)]">
          <p class="text-lg mb-2">Sin resultados</p>
          <p class="text-sm">La consulta no devolvió datos.</p>
        </div>
      )}
    </div>
  );
}
