// islands/Reportes.tsx
import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import Chart from "./Chart.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import {
  type ChartsListResponse,
  downloadReport,
  getReportDownloadUrl,
  getReportFileUrl,
  listCharts,
  listReports,
  type ReportInfo,
  type ReportsListResponse,
} from "../services/api.ts";
import { formatSize, REPORT_LABELS } from "../utils/reports.ts";
import { toast } from "../utils/toast.ts";

const CHART_NAMES: Record<string, string> = {
  resumen_ejecutivo: "Resumen ejecutivo",
  tasa_exito: "Tasa de éxito de matrícula",
  top_programas: "Top programas",
  distribucion_usuarios: "Distribución de usuarios",
  top_incidencias: "Top incidencias",
};

interface Props {
  executionId: number;
}

export default function Reportes({ executionId }: Props) {
  const meta = useSignal<ChartsListResponse | null>(null);
  const reports = useSignal<ReportsListResponse | null>(null);
  const downloading = useSignal<string | null>(null);
  const loading = useSignal(true);
  const error = useSignal("");

  useEffect(() => {
    if (!executionId) return;
    (async () => {
      try {
        const [chartsData, reportsData] = await Promise.all([
          listCharts(executionId),
          listReports(executionId),
        ]);
        meta.value = chartsData;
        reports.value = reportsData;
      } catch (e) {
        error.value = e instanceof Error
          ? e.message
          : "Error al cargar reportes";
      } finally {
        loading.value = false;
      }
    })();
  }, [executionId]);

  async function handleDownload(url: string, filename: string) {
    downloading.value = filename;
    try {
      await downloadReport(url, filename);
    } catch {
      toast("Error al descargar reporte", "error");
    } finally {
      downloading.value = null;
    }
  }

  if (loading.value) return <LoadingSkeleton variant="chart" />;
  if (error.value) return <ErrorBox message={error.value} />;

  const charts = Object.entries(CHART_NAMES).map(([id, title]) => ({
    id,
    title,
  }));

  return (
    <>
      {reports.value && reports.value.reports.length > 0 && (
        <section class="mb-10">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">
              Descargar reportes
            </h2>
            <button
              onClick={() =>
                handleDownload(
                  getReportDownloadUrl(executionId),
                  `reportes_ejecucion_${executionId}.zip`,
                )}
              disabled={downloading.value !== null}
              class="px-4 py-2 bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white rounded text-sm hover:brightness-110 disabled:opacity-50 flex items-center gap-2"
            >
              {downloading.value?.endsWith(".zip")
                ? (
                  <>
                    <span class="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />Descargando...
                  </>
                )
                : "📦 Descargar todo (ZIP)"}
            </button>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(reports.value.reports as ReportInfo[]).map((r) => {
              const label = REPORT_LABELS[r.name] || r.name;
              const isDownloading = downloading.value === r.filename;
              return (
                <button
                  onClick={() =>
                    handleDownload(
                      getReportFileUrl(executionId, r.name),
                      r.filename,
                    )}
                  disabled={downloading.value !== null}
                  class="text-left px-4 py-3 rounded border border-[var(--border-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-50 transition-colors"
                >
                  <div class="flex items-center gap-2">
                    <span>📄</span>
                    <span class="flex-1 text-sm font-medium text-[var(--text-primary)] truncate">
                      {label}
                    </span>
                    {isDownloading
                      ? (
                        <span class="inline-block w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin shrink-0" />
                      )
                      : (
                        <span class="text-xs text-[var(--text-secondary)] shrink-0">
                          {formatSize(r.size)}
                        </span>
                      )}
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <section>
        <div class="mb-4">
          <h2 class="text-lg font-semibold text-[var(--text-primary)]">
            Gráficos
          </h2>
          <p class="text-[var(--text-secondary)] text-sm">
            Visualización de datos generados con Plotly.js
          </p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          {charts.map(({ id, title }) => (
            <Chart
              key={id}
              executionId={executionId}
              chartName={id}
              title={title}
              height="380px"
            />
          ))}
        </div>
      </section>
    </>
  );
}
