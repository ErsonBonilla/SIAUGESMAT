// islands/DetalleLoteIsland.tsx
import { useComputed, useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  cancelBatch,
  getBatchStatus,
  type OperationBatchStatus,
  pauseBatch,
  resumeBatch,
} from "../services/api.ts";
import { formatDateTime, formatDuration } from "../utils/date.ts";
import { batchActionLabel, batchEntityLabel } from "../utils/batch-labels.ts";
import BatchReportsSection from "../components/BatchReportsSection.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";
import Pagination from "../components/Pagination.tsx";
import ProgressBar from "../components/ProgressBar.tsx";
import { SpinnerIcon } from "../utils/icons.tsx";
import { toast } from "../utils/toast.ts";

const PAGE_SIZE = 20;

interface Props {
  batchId: string;
}

export default function BatchDetailIsland({ batchId }: Props) {
  const status = useSignal<OperationBatchStatus | null>(null);
  const loading = useSignal(true);
  const errorMsg = useSignal("");
  const offset = useSignal(0);
  const pausing = useSignal(false);
  const resuming = useSignal(false);
  const cancelling = useSignal(false);

  const fetchStatus = async (newOffset = offset.value) => {
    try {
      const st = await getBatchStatus(batchId, newOffset, PAGE_SIZE);
      status.value = st;
      offset.value = st.offset;
    } catch (e) {
      errorMsg.value = e instanceof Error
        ? e.message
        : "Error al cargar el lote.";
    } finally {
      loading.value = false;
    }
  };

  useEffect(() => {
    fetchStatus(0);
  }, [batchId]);

  const isRunning = useComputed(() => {
    const s = status.value;
    if (!s) return false;
    return s.pending > 0 || s.processing > 0;
  });

  const isPaused = useComputed(() => (status.value?.paused ?? 0) > 0);
  const isCompleted = useComputed(() => !!status.value?.completed_at);
  const isCancelled = useComputed(() => (status.value?.cancelled ?? 0) > 0);

  useEffect(() => {
    if (!status.value || !isRunning.value) return;
    const interval = setInterval(async () => {
      try {
        const st = await getBatchStatus(batchId, offset.value, PAGE_SIZE);
        status.value = st;
        if (st.pending === 0 && st.processing === 0) clearInterval(interval);
      } catch {
        toast("Error al actualizar estado", "error");
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [batchId, isRunning.value]);

  const handlePageChange = (newOffset: number) => {
    fetchStatus(newOffset);
  };

  const handlePause = async () => {
    pausing.value = true;
    try {
      await pauseBatch(batchId);
      toast("Lote pausado", "success");
      fetchStatus();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al pausar", "error");
    } finally {
      pausing.value = false;
    }
  };

  const handleResume = async () => {
    resuming.value = true;
    try {
      await resumeBatch(batchId);
      toast("Lote reanudado", "success");
      fetchStatus();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al reanudar", "error");
    } finally {
      resuming.value = false;
    }
  };

  const handleCancel = async () => {
    if (
      !window.confirm(
        "¿Cancelar este lote? Se detendrá el procesamiento en curso.",
      )
    ) return;
    cancelling.value = true;
    try {
      await cancelBatch(batchId);
      toast("Lote cancelado", "success");
      fetchStatus();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al cancelar", "error");
    } finally {
      cancelling.value = false;
    }
  };

  if (loading.value) return <LoadingSkeleton variant="chart" />;
  if (errorMsg.value) return <ErrorBox message={errorMsg.value} />;
  if (!status.value) {
    return <p class="text-[var(--text-secondary)]">El lote no existe.</p>;
  }

  const s = status.value;
  const pct = s.total > 0
    ? Math.min(100, Math.round((s.completed + s.failed) / s.total * 100))
    : 100;
  const pendingCount = s.pending + s.processing;

  const durationSeconds = s.completed_at
    ? s.created_at
      ? (new Date(s.completed_at).getTime() -
        new Date(s.created_at).getTime()) /
        1000
      : null
    : null;

  const statusLabel = isCancelled.value
    ? "Cancelado"
    : isCompleted.value
    ? "Completado"
    : isPaused.value
    ? "Pausado"
    : isRunning.value
    ? "En ejecución"
    : "Pendiente";

  return (
    <>
      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 mb-6">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-semibold text-[var(--text-primary)] font-mono">
              Lote {batchId.slice(0, 12)}...
            </h2>
            <p class="text-sm text-[var(--text-secondary)]">
              {batchEntityLabel(s.entity_type)} · {batchActionLabel(s.action)}
              {s.modalidad ? ` · ${s.modalidad}` : ""}
            </p>
          </div>
          <div class="flex items-center gap-3">
            {isRunning.value && (
              <SpinnerIcon class="animate-spin h-4 w-4 text-[var(--accent)]" />
            )}
            <span class="text-sm font-medium">{statusLabel}</span>
          </div>
        </div>
        <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-[var(--text-secondary)]">Inicio</span>
            <p>{formatDateTime(s.created_at)}</p>
          </div>
          <div>
            <span class="text-[var(--text-secondary)]">Fin</span>
            <p>{formatDateTime(s.completed_at)}</p>
          </div>
          <div>
            <span class="text-[var(--text-secondary)]">Duración</span>
            <p>{formatDuration(durationSeconds)}</p>
          </div>
          <div>
            <span class="text-[var(--text-secondary)]">Progreso</span>
            <p class="font-medium">{pct}%</p>
          </div>
        </div>
      </div>

      {isCancelled.value && (
        <div class="bg-gray-50 border border-gray-300 rounded-2xl p-6 mb-6">
          <div class="flex items-center gap-3">
            <span class="text-2xl">✕</span>
            <div>
              <h3 class="text-lg font-bold text-gray-800">Lote cancelado</h3>
              <p class="text-sm text-gray-600">
                El lote fue cancelado por el usuario y no continuará su
                procesamiento.
              </p>
            </div>
          </div>
        </div>
      )}

      {(isRunning.value || isPaused.value) && (
        <>
          <ProgressBar
            currentPhase={isPaused.value
              ? "Lote pausado"
              : `Procesando ${
                batchEntityLabel(s.entity_type).toLowerCase()
              }...`}
            currentStep={1}
            progressPct={isPaused.value ? Math.min(99, pct) : pct}
            status={isPaused.value ? "paused" : "running"}
          />
          <div class="flex justify-end gap-2 mt-3">
            {isRunning.value && (
              <button
                type="button"
                onClick={handlePause}
                disabled={pausing.value}
                class="px-4 py-1.5 text-sm font-medium text-[var(--accent)] border border-[var(--accent)] rounded-lg hover:bg-[var(--accent)] hover:text-white transition disabled:opacity-50"
              >
                {pausing.value ? "Pausando..." : "⏸ Pausar"}
              </button>
            )}
            {isPaused.value && (
              <button
                type="button"
                onClick={handleResume}
                disabled={resuming.value}
                class="px-4 py-1.5 text-sm font-medium text-[var(--accent)] border border-[var(--accent)] rounded-lg hover:bg-[var(--accent)] hover:text-white transition disabled:opacity-50"
              >
                {resuming.value ? "Reanudando..." : "▶ Reanudar"}
              </button>
            )}
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling.value}
              class="px-4 py-1.5 text-sm font-medium text-red-500 border border-red-500 rounded-lg hover:bg-red-500 hover:text-white transition disabled:opacity-50"
            >
              {cancelling.value ? "Cancelando..." : "✕ Cancelar"}
            </button>
          </div>
        </>
      )}

      <div class="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-6">
        {[
          {
            label: "Total",
            value: s.total,
            color: "text-[var(--text-primary)]",
          },
          {
            label: "Completados",
            value: s.completed,
            color: "text-[var(--brand-green)]",
          },
          {
            label: "Fallidos",
            value: s.failed,
            color: "text-[var(--brand-red)]",
          },
          {
            label: "Pendientes",
            value: pendingCount,
            color: "text-yellow-600",
          },
          {
            label: "Cancelados",
            value: s.cancelled,
            color: "text-[var(--text-muted)]",
          },
        ].map((m) => (
          <div
            key={m.label}
            class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-4 text-center"
          >
            <div class={`text-2xl font-bold ${m.color}`}>{m.value}</div>
            <div class="text-xs text-[var(--text-secondary)] mt-1">
              {m.label}
            </div>
          </div>
        ))}
      </div>

      {isCompleted.value && (
        <div class="mb-6">
          <BatchReportsSection batchId={batchId} />
        </div>
      )}

      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
        <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
          Detalle de operaciones ({offset.value + 1}–{offset.value +
            s.details.length} de {s.total})
        </h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border-primary)]">
                <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                  {batchEntityLabel(s.entity_type).slice(0, -1)}
                </th>
                <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                  Estado
                </th>
                <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                  Error
                </th>
              </tr>
            </thead>
            <tbody>
              {s.details.map((d) => (
                <tr
                  key={d.identifier}
                  class="border-b border-[var(--border-primary)]"
                >
                  <td class="py-2 px-2 font-medium text-[var(--text-primary)] font-mono text-xs">
                    {d.identifier}
                  </td>
                  <td class="py-2 px-2">
                    {d.status === "completed" && (
                      <span class="text-[var(--brand-green)] text-xs font-medium">
                        ✓ Completado
                      </span>
                    )}
                    {d.status === "failed" && (
                      <span class="text-[var(--brand-red)] text-xs font-medium">
                        ✕ Fallido
                      </span>
                    )}
                    {d.status === "processing" && (
                      <span class="text-yellow-600 text-xs font-medium">
                        ◐ Procesando
                      </span>
                    )}
                    {d.status === "pending" && (
                      <span class="text-[var(--text-muted)] text-xs">
                        Pendiente
                      </span>
                    )}
                    {d.status === "paused" && (
                      <span class="text-[var(--text-muted)] text-xs">
                        Pausado
                      </span>
                    )}
                    {d.status === "cancelled" && (
                      <span class="text-[var(--text-muted)] text-xs">
                        Cancelado
                      </span>
                    )}
                  </td>
                  <td
                    class="py-2 px-2 text-xs text-[var(--text-muted)] max-w-xs truncate"
                    title={d.error_message ?? ""}
                  >
                    {d.error_message || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination
          offset={offset.value}
          pageSize={PAGE_SIZE}
          total={s.total}
          label="operaciones"
          onPageChange={handlePageChange}
        />
      </div>

      <div class="mt-6 flex gap-4">
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
