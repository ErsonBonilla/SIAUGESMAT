// islands/Reportes.tsx
import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import Chart from "./GraficoIsland.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import ReportCard from "../components/ReportCard.tsx";
import { useReports } from "../hooks/useReports.ts";
import {
  type ChartsListResponse,
  downloadReport,
  getReportDownloadUrl,
  getReportFileUrl,
  listCharts,
} from "../services/api.ts";
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
  const downloading = useSignal<string | null>(null);
  const loading = useSignal(true);
  const error = useSignal("");

  const {
    reports,
    loading: reportsLoading,
  } = useReports({ executionId });

  useEffect(() => {
    if (!executionId) return;
    (async () => {
      try {
        const chartsData = await listCharts(executionId);
        meta.value = chartsData;
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

  if (loading.value || reportsLoading.value) {
    return <LoadingSkeleton variant="chart" />;
  }
  if (error.value) return <ErrorBox message={error.value} />;

  const charts = Object.entries(CHART_NAMES).map(([id, title]) => ({
    id,
    title,
  }));

  return (
    <>
      {reports.value.length > 0 && (
        <section class="mb-10">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">
              Descargar reportes
            </h2>
            <button
              type="button"
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
            {reports.value.map((r) => (
              <ReportCard
                key={r.name}
                report={r}
                downloading={downloading.value === r.filename}
                disabled={downloading.value !== null}
                onClick={(report) =>
                  handleDownload(
                    getReportFileUrl(executionId, report.name),
                    report.filename,
                  )}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <div class="mb-4">
          <h2 class="text-lg font-semibold text-[var(--text-primary)]">
            Gráficos
          </h2>
          <p class="text-[var(--text-secondary)] text-sm">
            Visualización de datos generados con Chart.js
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
