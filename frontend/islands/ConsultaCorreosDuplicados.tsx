import { useComputed, useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  downloadReport,
  getQueryExportUrl,
  getQueryTaskStatus,
  queryEntities,
  type QueryTaskStatus,
} from "../services/api.ts";
import { DownloadIcon, SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import Pagination from "../components/Pagination.tsx";
import QueryHelp from "../components/QueryHelp.tsx";

const PAGE_SIZE = 20;

const COLUMNS = [
  { key: "email", label: "Correo" },
  { key: "username", label: "Username" },
  { key: "firstname", label: "Nombres" },
  { key: "lastname", label: "Apellidos" },
  { key: "user_id", label: "ID Moodle" },
  { key: "duplicate_count", label: "Nº de cuentas" },
];

interface DuplicateEmailRow {
  email: string;
  username: string;
  firstname: string;
  lastname: string;
  user_id: number | string;
  duplicate_count: number;
}

export default function CorreosDuplicadosQuery() {
  const data = useSignal<DuplicateEmailRow[]>([]);
  const loading = useSignal(false);
  const error = useSignal("");
  const taskId = useSignal("");
  const taskStatus = useSignal<QueryTaskStatus | null>(null);
  const pollingId = useSignal<number | null>(null);
  const started = useSignal(false);
  const pageOffset = useSignal(0);
  const totalItems = useSignal(0);
  const pageData = useComputed(() =>
    data.value.slice(pageOffset.value, pageOffset.value + PAGE_SIZE)
  );

  useEffect(() => {
    return () => {
      if (pollingId.value) clearInterval(pollingId.value);
    };
  }, []);

  const startQuery = async () => {
    loading.value = true;
    error.value = "";
    data.value = [];
    taskStatus.value = null;
    started.value = false;
    try {
      const result = await queryEntities("duplicate_emails", {});
      taskId.value = result.task_id;
      startPolling(result.task_id);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al consultar.";
      loading.value = false;
    }
  };

  const startPolling = (id: string) => {
    if (pollingId.value) clearInterval(pollingId.value);
    const fetchStatus = async () => {
      try {
        const status = await getQueryTaskStatus(id);
        taskStatus.value = status;
        if (status.status === "running") {
          started.value = true;
        } else if (status.status === "completed") {
          data.value = (status.result || []) as unknown as DuplicateEmailRow[];
          totalItems.value = data.value.length;
          pageOffset.value = 0;
          loading.value = false;
          if (pollingId.value) {
            clearInterval(pollingId.value);
            pollingId.value = null;
          }
        } else if (status.status === "failed") {
          error.value = status.error || "Error desconocido.";
          loading.value = false;
          if (pollingId.value) {
            clearInterval(pollingId.value);
            pollingId.value = null;
          }
        }
      } catch {
        //
      }
    };
    fetchStatus();
    pollingId.value = setInterval(fetchStatus, 2000);
  };

  const exportUrl = taskId.value ? getQueryExportUrl(taskId.value) : "";

  return (
    <div class="space-y-4">
      <QueryHelp
        sections={[
          {
            title: "Qué consulta",
            body:
              "Lista los correos que tienen más de un usuario registrado con ese correo en Moodle. Cada fila es una cuenta que comparte un correo duplicado.",
          },
          {
            title: "Cómo se encuentra la información",
            body: [
              "Moodle 3.9 no permite listar todos los usuarios por API, por lo que la consulta combina dos fuentes: los usuarios que la app ha creado o matriculado y los matriculados en cursos SIAUGESMAT.",
              "Luego re-consulta cada correo candidato en Moodle para capturar TODAS las cuentas que lo comparten, incluidas las que la app nunca procesó.",
              "La columna 'Nº de cuentas' indica cuántas cuentas comparten ese correo.",
            ],
          },
          {
            title: "Tiempo de ejecución",
            body: [
              "Esta consulta recorre todos los cursos SIAUGESMAT y puede tardar entre 15 y 25 minutos.",
            ],
          },
        ]}
      />

      <button
        type="button"
        onClick={startQuery}
        disabled={loading.value}
        class="px-4 py-1.5 bg-[var(--brand-green)] text-white rounded text-sm hover:brightness-90 disabled:opacity-60"
      >
        {loading.value
          ? (
            <span class="flex items-center gap-1.5">
              <SpinnerIcon class="animate-spin h-4 w-4" />
              Consultando...
            </span>
          )
          : "Consultar"}
      </button>

      {loading.value && started.value && (
        <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <SpinnerIcon class="animate-spin h-4 w-4" />
          <span>
            Consultando Moodle (procesando {taskStatus.value?.total_count || 0}
            {" "}
            ítems)... puede tardar varios minutos.
          </span>
        </div>
      )}

      {error.value && <ErrorBox message={error.value} />}

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
                downloadReport(exportUrl, "correos_duplicados.csv").catch(
                  () => {},
                )}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-tertiary)] text-[var(--text-primary)] rounded text-sm font-medium no-underline hover:bg-[var(--border-secondary)] transition cursor-pointer"
            >
              <DownloadIcon class="w-4 h-4" />
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
                {COLUMNS.map((col) => (
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
              {data.value.length === 0
                ? (
                  <tr>
                    <td
                      colSpan={COLUMNS.length}
                      class="py-12 text-center text-[var(--text-muted)]"
                    >
                      {started.value
                        ? "No se encontraron correos duplicados."
                        : 'Presione "Consultar" para buscar correos con más de un usuario.'}
                    </td>
                  </tr>
                )
                : pageData.value.map((row, idx) => (
                  <tr
                    key={idx}
                    class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
                  >
                    <td class="py-2 px-3 text-[var(--text-primary)] font-medium">
                      {row.email}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.username}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.firstname || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.lastname || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.user_id}
                    </td>
                    <td class="py-2 px-3">
                      <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--brand-red)]/10 text-[var(--brand-red)]">
                        {row.duplicate_count}
                      </span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading.value && !error.value && data.value.length > PAGE_SIZE && (
        <Pagination
          offset={pageOffset.value}
          pageSize={PAGE_SIZE}
          total={totalItems.value}
          label="resultados"
          onPageChange={(o) => {
            pageOffset.value = o;
          }}
        />
      )}
    </div>
  );
}
