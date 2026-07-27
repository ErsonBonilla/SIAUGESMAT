import { SpinnerIcon, CheckIcon, XMarkIcon } from "../utils/icons.tsx";
import { getBatchReportUrl, downloadReport } from "../services/api.ts";
import type { OperationBatchStatus } from "../services/api/types.ts";
import Pagination from "./Pagination.tsx";

interface BatchProgressTableProps {
  batchStatus: OperationBatchStatus;
  batchId: string;
  labelSingular: string;
  labelPlural: string;
  pagination?: {
    offset: number;
    pageSize: number;
    onPageChange: (offset: number) => void;
  };
}

export default function BatchProgressTable({ batchStatus, batchId, labelSingular, labelPlural, pagination }: BatchProgressTableProps) {
  return (
    <div class="mt-6 bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
      <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">Progreso del lote {batchId.slice(0, 8)}...</h3>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-5 mb-6">
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--text-primary)]">{batchStatus.total}</div>
          <div class="text-xs text-[var(--text-secondary)]">Total</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--brand-green)]">{batchStatus.completed}</div>
          <div class="text-xs text-[var(--text-secondary)]">Completados</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--brand-red)]">{batchStatus.failed}</div>
          <div class="text-xs text-[var(--text-secondary)]">Fallidos</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-yellow-600">{batchStatus.processing + batchStatus.pending}</div>
          <div class="text-xs text-[var(--text-secondary)]">Pendientes</div>
        </div>
      </div>

      {batchStatus.pending > 0 || batchStatus.processing > 0 ? (
        <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <SpinnerIcon class="animate-spin h-4 w-4" />
          <span>Procesando {labelPlural}...</span>
        </div>
      ) : (
        <div class="flex flex-col sm:flex-row sm:items-center gap-3">
          <div class="flex items-center gap-2 text-sm text-[var(--brand-green)]">
            <CheckIcon class="w-4 h-4" />
            <span>Procesamiento completado</span>
          </div>
          <button
            onClick={() => downloadReport(getBatchReportUrl(batchId), `reportes_${batchId.slice(0, 8)}.zip`)}
            class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white text-sm font-medium no-underline hover:brightness-110 transition cursor-pointer"
          >
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" class="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>Descargar reportes (CSV)</span>
          </button>
        </div>
      )}

      <div class="mt-6 overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--border-primary)]">
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">{labelSingular}</th>
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">Estado</th>
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">Error</th>
            </tr>
          </thead>
          <tbody>
            {batchStatus.details.map((d) => (
              <tr key={d.identifier} class="border-b border-[var(--border-primary)]">
                <td class="py-2 px-2 font-medium text-[var(--text-primary)]">{d.identifier}</td>
                <td class="py-2 px-2">
                  {d.status === "completed" && <span class="flex items-center gap-1 text-[var(--brand-green)]"><CheckIcon class="w-3 h-3" />Completado</span>}
                  {d.status === "failed" && <span class="flex items-center gap-1 text-[var(--brand-red)]"><XMarkIcon class="w-3 h-3" />Fallido</span>}
                  {d.status === "processing" && <span class="flex items-center gap-1 text-yellow-600"><SpinnerIcon class="animate-spin w-3 h-3" />Procesando</span>}
                  {d.status === "pending" && <span class="text-[var(--text-muted)]">Pendiente</span>}
                </td>
                <td class="py-2 px-2 text-xs text-[var(--text-muted)] whitespace-nowrap">{d.error_message || "—"}</td>
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
