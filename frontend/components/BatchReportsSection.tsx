import { downloadReport, getBatchReportFileUrl, getBatchReportUrl } from "../services/api.ts";

const BATCH_REPORT_LABELS: Record<string, string> = {
  resultados: "Resultados",
  fallidos: "Fallidos",
  creados: "Creados",
  no_encontrados: "No encontrados",
  resumen: "Resumen",
};

const BATCH_REPORT_NAMES = [
  "resultados",
  "fallidos",
  "creados",
  "no_encontrados",
  "resumen",
] as const;

interface BatchReportsSectionProps {
  batchId: string;
}

export default function BatchReportsSection(
  { batchId }: BatchReportsSectionProps,
) {
  const shortId = batchId.slice(0, 8);

  return (
    <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
      <div class="flex items-center justify-between gap-4 mb-3">
        <div>
          <h3 class="text-lg font-semibold text-[var(--text-primary)]">
            Reportes
          </h3>
          <p class="text-sm text-[var(--text-secondary)]">
            Descargue los reportes generados al finalizar el lote.
          </p>
        </div>
        <button
          type="button"
          onClick={() =>
            downloadReport(
              getBatchReportUrl(batchId),
              `reportes_${shortId}.zip`,
            )}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white text-xs font-medium hover:brightness-110 transition cursor-pointer"
        >
          <svg
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            class="w-3.5 h-3.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          ZIP
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        {BATCH_REPORT_NAMES.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() =>
              downloadReport(
                getBatchReportFileUrl(batchId, name),
                `${name}.csv`,
              )}
            class="px-2.5 py-1 rounded border border-[var(--border-secondary)] text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent)] transition cursor-pointer bg-[var(--bg-primary)]"
          >
            {BATCH_REPORT_LABELS[name] ?? name}.csv
          </button>
        ))}
      </div>
    </div>
  );
}
