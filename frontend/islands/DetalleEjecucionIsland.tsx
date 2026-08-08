// islands/DetalleEjecucionIsland.tsx
import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import Pagination from "../components/Pagination.tsx";
import ProgressBar from "../components/ProgressBar.tsx";
import ReportsSection from "../components/ReportsSection.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import {
  cancelExecution,
  confirmExecution,
  type ErrorLog,
  type Execution,
  getExecution,
  getExecutionErrors,
  pauseExecution,
  resumeExecution,
} from "../services/api.ts";
import { formatDateTime, formatDuration } from "../utils/date.ts";
import { toast } from "../utils/toast.ts";
import { MODE_LABELS, STATUS_LABELS } from "../utils/constants.ts";

const ERROR_TYPE_LABELS: Record<string, string> = {
  "1": "FASE 1 — Consulta",
  "2": "FASE 2 — Análisis",
  "3": "FASE 3 — Estructura",
  "4": "FASE 4 — Personas",
  "critical": "Error crítico",
};

const ERRORS_PAGE_SIZE = 20;

const THRESHOLD_YELLOW = 1.0;
const THRESHOLD_RED = 5.0;

function computeSemaphore(
  execution: Execution,
): { color: string; text: string } {
  if (execution.status === "failed") return { color: "red", text: "Fallido" };
  if (execution.status === "cancelled") {
    return { color: "gray", text: "Cancelado" };
  }
  if (execution.status !== "completed") {
    return { color: "gray", text: "Sin finalizar" };
  }
  const total = execution.metrics?.total_operations ??
    ((execution.metrics?.courses_created || 0) +
      (execution.metrics?.users_created || 0) +
      (execution.metrics?.enrolments || 0));
  if (!total) return { color: "gray", text: "Sin datos" };
  const errorRate = ((execution.errors_count || 0) / total) * 100;
  if (errorRate >= THRESHOLD_RED || (execution.duration_seconds || 0) >= 7200) {
    return { color: "red", text: "Crítico" };
  }
  if (
    errorRate >= THRESHOLD_YELLOW || (execution.duration_seconds || 0) >= 3600
  ) return { color: "yellow", text: "Advertencia" };
  return { color: "green", text: "Exitoso" };
}

interface Props {
  executionId: number;
}

export default function JobDetailIsland({ executionId }: Props) {
  const execution = useSignal<Execution | null>(null);
  const errors = useSignal<ErrorLog[]>([]);
  const loading = useSignal(true);
  const errorMsg = useSignal("");
  const errorOffset = useSignal(0);
  const confirming = useSignal(false);
  const pausing = useSignal(false);
  const resuming = useSignal(false);
  const cancelling = useSignal(false);

  useEffect(() => {
    (async () => {
      try {
        const [exec, errorList] = await Promise.all([
          getExecution(executionId),
          getExecutionErrors(executionId, ERRORS_PAGE_SIZE, 0),
        ]);
        execution.value = exec;
        errors.value = errorList;
      } catch (e) {
        errorMsg.value = e instanceof Error ? e.message : "Error al cargar.";
      } finally {
        loading.value = false;
      }
    })();
  }, [executionId]);

  useEffect(() => {
    const runningStatuses = ["queued", "running"];
    if (!execution.value || !runningStatuses.includes(execution.value.status)) {
      return;
    }
    const interval = setInterval(async () => {
      try {
        const exec = await getExecution(executionId);
        execution.value = exec;
        if (!runningStatuses.includes(exec.status)) clearInterval(interval);
        if (
          exec.errors_count > errors.value.length && errorOffset.value === 0
        ) {
          const fresh = await getExecutionErrors(
            executionId,
            ERRORS_PAGE_SIZE,
            0,
          );
          if (fresh.length > 0) errors.value = fresh;
        }
      } catch {
        toast("Error al actualizar estado", "error");
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [executionId, execution.value?.status]);

  const fetchErrorsPage = async (offset: number) => {
    try {
      const page = await getExecutionErrors(
        executionId,
        ERRORS_PAGE_SIZE,
        offset,
      );
      if (page.length > 0) {
        errors.value = page;
        errorOffset.value = offset;
      }
    } catch {
      toast("Error al cargar errores", "error");
    }
  };

  const handleErrorPageChange = (offset: number) => {
    fetchErrorsPage(offset);
  };

  if (loading.value) return <LoadingSkeleton variant="chart" />;
  if (errorMsg.value) return <ErrorBox message={errorMsg.value} />;

  const exec = execution.value!;
  if (!exec) {
    return <p class="text-[var(--text-secondary)]">La ejecución no existe.</p>;
  }

  const semaphore = computeSemaphore(exec);

  return (
    <>
      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 mb-6">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2
              class="text-lg font-semibold text-[var(--text-primary)] truncate max-w-[400px]"
              title={exec.filename}
            >
              {exec.filename}
            </h2>
            <p class="text-sm text-[var(--text-secondary)]">
              Semestre {exec.semester} · Modo{" "}
              {MODE_LABELS[exec.mode] || exec.mode}
            </p>
          </div>
          <div class="flex items-center gap-3">
            <span
              class={`inline-block w-3 h-3 rounded-full ${
                semaphore.color === "green"
                  ? "bg-[var(--brand-green)]"
                  : semaphore.color === "yellow"
                  ? "bg-[#F59E0B]"
                  : semaphore.color === "red"
                  ? "bg-[var(--brand-red)]"
                  : "bg-[var(--text-muted)]"
              }`}
            />
            <span class="text-sm font-medium">{semaphore.text}</span>
          </div>
        </div>
        <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-[var(--text-secondary)]">Estado</span>
            <p class="font-medium">
              {(exec.status === "running" || exec.status === "queued") &&
                  (exec.current_phase || "").includes("reintento")
                ? "Reintentando..."
                : STATUS_LABELS[exec.status] || exec.status}
            </p>
          </div>
          <div>
            <span class="text-[var(--text-secondary)]">Inicio</span>
            <p>{formatDateTime(exec.started_at)}</p>
          </div>
          <div>
            <span class="text-[var(--text-secondary)]">Fin</span>
            <p>{formatDateTime(exec.completed_at)}</p>
          </div>
          <div>
            <span class="text-[var(--text-secondary)]">Duración</span>
            <p>{formatDuration(exec.duration_seconds)}</p>
          </div>
        </div>
      </div>

      {exec.status === "cancelled" && (
        <div class="bg-gray-50 border border-gray-300 rounded-2xl p-6 mb-6">
          <div class="flex items-center gap-3">
            <span class="text-2xl">✕</span>
            <div>
              <h3 class="text-lg font-bold text-gray-800">
                Ejecución cancelada
              </h3>
              <p class="text-sm text-gray-600">
                La ejecución fue cancelada por el usuario y no continuará su
                procesamiento.
              </p>
            </div>
          </div>
        </div>
      )}

      {exec.status === "review_required" && (
        <div class="bg-orange-50 border border-orange-300 rounded-2xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-3">
            <span class="text-2xl">⚠️</span>
            <div>
              <h3 class="text-lg font-bold text-orange-800">
                Revisión requerida — Eliminación masiva
              </h3>
              <p class="text-sm text-orange-700">
                El plan incluye la eliminación de{" "}
                <strong>
                  {exec.metrics?.pending_delete_count ?? "varios"}
                </strong>{" "}
                cursos. Esta acción requiere confirmación explícita antes de
                continuar.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={async () => {
              if (
                !window.confirm(
                  "¿Confirmar la eliminación masiva de cursos? Esta acción es irreversible.",
                )
              ) return;
              confirming.value = true;
              try {
                await confirmExecution(exec.id);
                toast("Procesamiento reanudado", "success");
                setTimeout(() => globalThis.location.reload(), 1500);
              } catch (e) {
                toast(
                  e instanceof Error ? e.message : "Error al confirmar",
                  "error",
                );
              } finally {
                confirming.value = false;
              }
            }}
            disabled={confirming.value}
            class="bg-orange-600 hover:bg-orange-700 text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition-all disabled:opacity-50"
          >
            {confirming.value ? "Confirmando…" : "Confirmar eliminación masiva"}
          </button>
        </div>
      )}

      {["queued", "running", "paused"].includes(exec.status) && (
        <>
          <ProgressBar
            currentPhase={exec.current_phase ?? null}
            currentStep={exec.current_step ?? null}
            progressPct={exec.progress_pct ?? 0}
            etaSeconds={exec.eta_seconds ?? undefined}
            status={exec.status}
          />
          {exec.status === "running" && (
            <div class="flex justify-end mt-3">
              <button
                type="button"
                onClick={async () => {
                  pausing.value = true;
                  try {
                    await pauseExecution(exec.id);
                    toast("Ejecución pausada", "success");
                    setTimeout(() => globalThis.location.reload(), 1000);
                  } catch (e) {
                    toast(
                      e instanceof Error ? e.message : "Error al pausar",
                      "error",
                    );
                  } finally {
                    pausing.value = false;
                  }
                }}
                disabled={pausing.value}
                class="px-4 py-1.5 text-sm font-medium text-[var(--accent)] border border-[var(--accent)] rounded-lg hover:bg-[var(--accent)] hover:text-white transition disabled:opacity-50"
              >
                {pausing.value ? "Pausando..." : "⏸ Pausar"}
              </button>
            </div>
          )}
          {exec.status === "paused" && (
            <div class="flex justify-end mt-3">
              <button
                type="button"
                onClick={async () => {
                  resuming.value = true;
                  try {
                    await resumeExecution(exec.id);
                    toast("Ejecución reanudada", "success");
                    setTimeout(() => globalThis.location.reload(), 1000);
                  } catch (e) {
                    toast(
                      e instanceof Error ? e.message : "Error al reanudar",
                      "error",
                    );
                  } finally {
                    resuming.value = false;
                  }
                }}
                disabled={resuming.value}
                class="px-4 py-1.5 text-sm font-medium text-[var(--accent)] border border-[var(--accent)] rounded-lg hover:bg-[var(--accent)] hover:text-white transition disabled:opacity-50"
              >
                {resuming.value ? "Reanudando..." : "▶ Reanudar"}
              </button>
            </div>
          )}
          {["running", "paused", "queued"].includes(exec.status) && (
            <div class="flex justify-end mt-3">
              <button
                type="button"
                onClick={async () => {
                  if (
                    !window.confirm(
                      "¿Cancelar esta ejecución? Se detendrá el procesamiento en curso.",
                    )
                  ) return;
                  cancelling.value = true;
                  try {
                    await cancelExecution(exec.id);
                    toast("Ejecución cancelada", "success");
                    setTimeout(() => globalThis.location.reload(), 1000);
                  } catch (e) {
                    toast(
                      e instanceof Error ? e.message : "Error al cancelar",
                      "error",
                    );
                  } finally {
                    cancelling.value = false;
                  }
                }}
                disabled={cancelling.value}
                class="px-4 py-1.5 text-sm font-medium text-red-500 border border-red-500 rounded-lg hover:bg-red-500 hover:text-white transition disabled:opacity-50"
              >
                {cancelling.value ? "Cancelando..." : "✕ Cancelar"}
              </button>
            </div>
          )}
        </>
      )}

      {exec.status === "completed" && (
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          {[
            {
              label: "Cursos creados",
              value: exec.metrics?.courses_created,
              color: "text-[var(--brand-green)]",
            },
            {
              label: "Cursos actualizados",
              value: exec.metrics?.courses_updated,
              color: "text-[var(--accent)]",
            },
            {
              label: "Cursos eliminados",
              value: exec.metrics?.courses_deleted,
              color: "text-[var(--brand-red)]",
            },
            {
              label: "Usuarios creados",
              value: exec.metrics?.users_created,
              color: "text-[var(--accent)]",
            },
            {
              label: "Matrículas",
              value: exec.metrics?.enrollments,
              color: "text-[#F59E0B]",
            },
            {
              label: "Errores",
              value: exec.errors_count,
              color: "text-[var(--brand-red)]",
            },
            {
              label: "Categorías creadas",
              value: exec.metrics?.categories_created,
              color: "text-[var(--text-secondary)]",
            },
          ].map((m) => (
            <div
              key={m.label}
              class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-4 text-center"
            >
              <div class={`text-2xl font-bold ${m.color}`}>
                {m.value ?? "—"}
              </div>
              <div class="text-xs text-[var(--text-secondary)] mt-1">
                {m.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {exec.status === "completed" && <ReportsSection executionId={exec.id} />}

      {errors.value.length > 0 && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 mb-6">
          <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
            Errores registrados ({errorOffset.value + 1}–{errorOffset.value +
              errors.value.length} de {exec.errors_count ?? 0})
          </h3>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-primary)]">
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                    Fase
                  </th>
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                    Identificador
                  </th>
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                    Mensaje
                  </th>
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                    Fecha
                  </th>
                </tr>
              </thead>
              <tbody>
                {errors.value.map((err) => (
                  <tr
                    key={err.id}
                    class="border-b border-[var(--border-primary)]"
                  >
                    <td class="py-2 px-2 text-xs font-medium text-[var(--brand-red)] whitespace-nowrap">
                      {ERROR_TYPE_LABELS[err.type] || err.type}
                    </td>
                    <td class="py-2 px-2 text-xs text-[var(--text-secondary)] font-mono">
                      {err.identifier || "—"}
                    </td>
                    <td
                      class="py-2 px-2 text-sm text-[var(--text-secondary)] max-w-xs truncate"
                      title={err.message ?? ""}
                    >
                      {err.message || "—"}
                    </td>
                    <td class="py-2 px-2 text-xs text-[var(--text-muted)] whitespace-nowrap">
                      {formatDateTime(err.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            offset={errorOffset.value}
            pageSize={ERRORS_PAGE_SIZE}
            total={exec.errors_count ?? 0}
            label="errores"
            onPageChange={handleErrorPageChange}
          />
        </div>
      )}

      <div class="mt-6 flex gap-4">
        <a href="/panel" class="gradient-text hover:underline text-sm">
          ← Volver al dashboard
        </a>
        <a
          href="/operaciones/ejecuciones"
          class="gradient-text hover:underline text-sm"
        >
          ← Volver a ejecuciones
        </a>
        <a
          href="/operaciones/historico"
          class="gradient-text hover:underline text-sm"
        >
          Ver histórico
        </a>
      </div>
    </>
  );
}
