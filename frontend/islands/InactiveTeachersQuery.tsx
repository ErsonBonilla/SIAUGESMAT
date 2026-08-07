import { useComputed, useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  downloadReport,
  getQueryExportUrl,
  getQueryTaskStatus,
  type InactiveTeacherRow,
  queryEntities,
  type QueryTaskStatus,
} from "../services/api.ts";
import { DownloadIcon, SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import Pagination from "../components/Pagination.tsx";
import SemesterPicker from "../components/SemesterPicker.tsx";

const PAGE_SIZE = 20;

const COLUMNS = [
  { key: "teacher_name", label: "Docente" },
  { key: "username", label: "Username" },
  { key: "email", label: "Correo" },
  { key: "course_name", label: "Curso" },
  { key: "program", label: "Programa" },
  { key: "cat", label: "CAT" },
  { key: "last_access", label: "Último acceso" },
  { key: "days_since_last_access", label: "Días sin acceso" },
];

function formatLastAccess(ts: number): string {
  if (!ts || ts <= 0) return "Nunca";
  return new Date(ts * 1000).toLocaleString();
}

function formatDaysSince(daysSince?: number): string {
  if (!daysSince || daysSince <= 0) return "Nunca";
  return `${daysSince} d`;
}

type CutoffMode = "days" | "months" | "years" | "semester";

export default function InactiveTeachersQuery() {
  const cutoffMode = useSignal<CutoffMode>("days");
  const semester = useSignal("");
  const days = useSignal(15);
  const months = useSignal(1);
  const years = useSignal(1);
  const data = useSignal<InactiveTeacherRow[]>([]);
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
    loading.value = true;
    error.value = "";
    data.value = [];
    taskStatus.value = null;
    started.value = false;
    try {
      const result = await queryEntities("inactive_teachers", params);
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
          data.value = (status.result || []) as unknown as InactiveTeacherRow[];
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
      <div class="flex flex-col sm:flex-row sm:items-end gap-4">
        <div class="flex flex-col gap-2">
          <div class="flex gap-1 bg-[var(--bg-tertiary)] rounded-lg p-1 w-fit flex-wrap">
            {(["days", "months", "years", "semester"] as const).map((mode) => {
              const labels: Record<CutoffMode, string> = {
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
                Días sin acceso (mínimo)
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
                Meses sin acceso (mínimo)
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
                Años sin acceso (mínimo)
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
              <SemesterPicker
                value={semester.value}
                onChange={(s) => {
                  semester.value = s;
                  error.value = "";
                }}
                minYear={2020}
              />
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={startQuery}
          disabled={loading.value ||
            (cutoffMode.value === "days" &&
              (!Number.isInteger(days.value) || days.value < 1 || days.value > 30)) ||
            (cutoffMode.value === "months" &&
              (!Number.isInteger(months.value) || months.value < 1 || months.value > 12)) ||
            (cutoffMode.value === "years" && (!Number.isInteger(years.value) || years.value < 1)) ||
            (cutoffMode.value === "semester" && !semester.value)}
          class="px-3 py-1.5 bg-[var(--brand-green)] text-white rounded text-sm hover:brightness-90 disabled:opacity-60 self-start mt-6"
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
      </div>

      {loading.value && started.value && (
        <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <SpinnerIcon class="animate-spin h-4 w-4" />
          <span>
            Consultando Moodle (procesando {taskStatus.value?.total_count || 0}
            {" "}
            cursos)... puede tardar varios minutos.
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
                downloadReport(exportUrl, "docentes_inactivos.csv").catch(
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
              {data.value.length === 0 && !loading.value
                ? (
                  <tr>
                    <td
                      colSpan={COLUMNS.length}
                      class="py-12 text-center text-[var(--text-muted)]"
                    >
                      Seleccione el corte (días o semestre) y presione "Consultar".
                    </td>
                  </tr>
                )
                : pageData.value.map((row, idx) => (
                  <tr
                    key={idx}
                    class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
                  >
                    <td class="py-2 px-3 text-[var(--text-primary)] font-medium">
                      {row.teacher_name || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.username}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.email}
                    </td>
                    <td
                      class="py-2 px-3 text-[var(--text-primary)] max-w-xs truncate"
                      title={row.course_name}
                    >
                      {row.course_name}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.program || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.cat || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {formatLastAccess(row.last_access)}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {formatDaysSince(row.days_since_last_access)}
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
