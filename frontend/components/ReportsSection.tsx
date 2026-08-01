import { useEffect } from "preact/hooks";
import { useSignal } from "@preact/signals";
import {
  downloadReport,
  getReportDownloadUrl,
  getReportFileUrl,
  listReports,
  type ReportInfo,
} from "../services/api.ts";
import Button from "./Button.tsx";
import LoadingSkeleton from "./LoadingSkeleton.tsx";
import { formatSize, REPORT_LABELS } from "../utils/reports.ts";

const REPORT_GROUPS = [
  {
    label: "Incidencias",
    icon: "⚠️",
    keys: [
      "inc_usuarios_inactivos",
      "inc_cursos_recientes",
      "inc_plantilla_no_encontrada",
      "inc_correos_duplicados",
    ],
  },
  {
    label: "Auditoría",
    icon: "📋",
    keys: [
      "audit_categorias_creadas",
      "audit_cursos_creados",
      "audit_cursos_eliminados",
      "audit_cursos_ocultados",
      "audit_cursos_renombrados",
      "audit_cursos_activados",
      "audit_usuarios",
      "audit_matriculas",
      "audit_conflictos_identidad",
      "audit_plan_acciones",
      "audit_errores",
    ],
  },
  {
    label: "Resumen",
    icon: "📊",
    keys: ["resumen_ejecutivo"],
  },
];

interface ReportsSectionProps {
  executionId: number;
}

export default function ReportsSection({ executionId }: ReportsSectionProps) {
  const open = useSignal(false);
  const reports = useSignal<ReportInfo[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");

  useEffect(() => {
    loading.value = true;
    listReports(executionId)
      .then((data) => {
        reports.value = data.reports;
      })
      .catch((e) => {
        error.value = e instanceof Error
          ? e.message
          : "Error al cargar reportes.";
      })
      .finally(() => {
        loading.value = false;
      });
  }, [executionId]);

  if (loading.value) return <LoadingSkeleton />;
  if (error.value || reports.value.length === 0) return null;

  const reportsMap = new Map(reports.value.map((r) => [r.name, r]));

  const handleDownload = (name: string, filename: string) => {
    downloadReport(getReportFileUrl(executionId, name), filename);
  };

  const handleDownloadAll = () => {
    downloadReport(
      getReportDownloadUrl(executionId),
      `reportes_ejecucion_${executionId}.zip`,
    );
  };

  return (
    <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-2xl p-6 mb-6">
      <button
        onClick={() => (open.value = !open.value)}
        class="w-full flex items-center justify-between gap-2 text-left cursor-pointer bg-transparent border-none p-0"
      >
        <div class="flex items-center gap-2">
          <span class="text-lg">📋</span>
          <span class="text-sm font-semibold text-[var(--text-primary)]">
            Reportes ({reports.value.length} archivos)
          </span>
        </div>
        <span
          class="text-sm text-[var(--text-muted)] transition-transform duration-300"
          style={{ transform: open.value ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          ▼
        </span>
      </button>

      {open.value && (
        <div class="mt-4 space-y-4 animate-scaleIn">
          <Button
            variant="primary"
            onClick={handleDownloadAll}
            style={{
              width: "100%",
              borderRadius: "0.75rem",
              padding: "0.625rem 1rem",
            }}
          >
            <span>📦</span>
            <span>Descargar todo (ZIP)</span>
          </Button>

          {REPORT_GROUPS.map((group) => {
            const groupReports = group.keys
              .map((k) => reportsMap.get(k))
              .filter((r): r is ReportInfo =>
                r !== undefined
              );
            if (groupReports.length === 0) return null;

            return (
              <div key={group.label}>
                <p class="text-xs font-semibold text-[var(--text-secondary)] mb-2 flex items-center gap-1">
                  <span>{group.icon}</span>
                  <span>{group.label}</span>
                </p>
                <div class="space-y-1 stagger-list">
                  {groupReports.map((r) => (
                    <button
                      key={r.name}
                      onClick={() => handleDownload(r.name, r.filename)}
                      class="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm transition cursor-pointer border-none report-row"
                    >
                      <span class="truncate">
                        {REPORT_LABELS[r.name] ?? r.name}
                      </span>
                      <span class="shrink-0 flex items-center gap-2">
                        <span class="text-xs text-[var(--text-muted)]">
                          {formatSize(r.size)}
                        </span>
                        <span>📥</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
