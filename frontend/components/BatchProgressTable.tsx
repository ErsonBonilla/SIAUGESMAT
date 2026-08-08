import { CheckIcon, SpinnerIcon, XMarkIcon } from "../utils/icons.tsx";
import type { OperationBatchStatus } from "../services/api.ts";
import BatchReportsSection from "./BatchReportsSection.tsx";
import Pagination from "./Pagination.tsx";
import ProgressBar from "./ProgressBar.tsx";

interface BatchProgressTableProps {
  batchStatus: OperationBatchStatus;
  batchId: string;
  labelSingular: string;
  labelPlural: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  pagination?: {
    offset: number;
    pageSize: number;
    onPageChange: (offset: number) => void;
  };
}

export default function BatchProgressTable(
  {
    batchStatus,
    batchId,
    labelSingular,
    labelPlural,
    onPause,
    onResume,
    onCancel,
    pagination,
  }: BatchProgressTableProps,
) {
  return (
    <div class="mt-6 bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
      <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
        Progreso del lote {batchId.slice(0, 8)}...
      </h3>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-5 mb-6">
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--text-primary)]">
            {batchStatus.total}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Total</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--brand-green)]">
            {batchStatus.completed}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Completados</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--brand-red)]">
            {batchStatus.failed}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Fallidos</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-yellow-600">
            {batchStatus.processing + batchStatus.pending}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Pendientes</div>
        </div>
      </div>

      {(() => {
        const total = batchStatus.total || 1;
        const done = batchStatus.completed + batchStatus.failed;
        const pct = Math.round(done / total * 100);
        const running = batchStatus.pending > 0 || batchStatus.processing > 0;
        return (
          <>
            <ProgressBar
              currentPhase={running
                ? `Procesando ${labelPlural}...`
                : `${labelSingular} procesados`}
              currentStep={running ? 1 : 4}
              progressPct={running ? pct : 100}
              status={running ? "running" : "completed"}
            />
            {!running && (
              <div class="mt-4">
                <BatchReportsSection batchId={batchId} />
                <a
                  href={`/operaciones/lotes/${batchId}`}
                  class="mt-3 inline-block text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] no-underline"
                >
                  Ver detalle completo →
                </a>
              </div>
            )}
          </>
        );
      })()}

      {(batchStatus.pending > 0 || batchStatus.processing > 0 ||
        batchStatus.paused > 0) && (
        <div class="flex justify-end gap-2 mt-3">
          {(batchStatus.pending > 0 || batchStatus.processing > 0) && onPause &&
            (
              <button
                type="button"
                onClick={onPause}
                class="px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-400 hover:bg-amber-500 text-white transition"
              >
                ⏸ Pausa
              </button>
            )}
          {batchStatus.paused > 0 && onResume && (
            <button
              type="button"
              onClick={onResume}
              class="px-3 py-1.5 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-700 text-white transition"
            >
              ▶ Reanudar
            </button>
          )}
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              class="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition"
            >
              ✖ Cancelar
            </button>
          )}
        </div>
      )}

      <div class="mt-6 overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--border-primary)]">
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                {labelSingular}
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
            {batchStatus.details.map((d) => (
              <tr
                key={d.identifier}
                class="border-b border-[var(--border-primary)]"
              >
                <td class="py-2 px-2 font-medium text-[var(--text-primary)]">
                  {d.identifier}
                </td>
                <td class="py-2 px-2">
                  {d.status === "completed" && (
                    <span class="flex items-center gap-1 text-[var(--brand-green)]">
                      <CheckIcon class="w-3 h-3" />Completado
                    </span>
                  )}
                  {d.status === "failed" && (
                    <span class="flex items-center gap-1 text-[var(--brand-red)]">
                      <XMarkIcon class="w-3 h-3" />Fallido
                    </span>
                  )}
                  {d.status === "processing" && (
                    <span class="flex items-center gap-1 text-yellow-600">
                      <SpinnerIcon class="animate-spin w-3 h-3" />Procesando
                    </span>
                  )}
                  {d.status === "pending" && (
                    <span class="text-[var(--text-muted)]">Pendiente</span>
                  )}
                </td>
                <td class="py-2 px-2 text-xs text-[var(--text-muted)] whitespace-nowrap">
                  {d.error_message || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pagination && (
        <Pagination
          offset={pagination.offset}
          pageSize={pagination.pageSize}
          total={batchStatus.total}
          label="registros"
          onPageChange={pagination.onPageChange}
        />
      )}
    </div>
  );
}
