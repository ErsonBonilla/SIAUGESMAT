import { useSignal } from "@preact/signals";
import { useReportes } from "../hooks/useReportes.ts";
import type { InfoReporte } from "../services/api.ts";
import Boton from "./Boton.tsx";
import EsqueletoCarga from "./EsqueletoCarga.tsx";
import { ETIQUETAS_REPORTES, formatearTamano } from "../utils/reportes.ts";

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
      "usuarios_creados_manual",
      "audit_errores",
    ],
  },
  {
    label: "Resumen",
    icon: "📊",
    keys: ["resumen_ejecutivo"],
  },
];

interface PropsSeccionReportes {
  executionId: number;
}

export default function SeccionReportes({ executionId }: PropsSeccionReportes) {
  const open = useSignal(false);
  const { reports, loading, error, download, descargarTodos } = useReportes({
    executionId,
  });

  if (loading.value) return <EsqueletoCarga />;
  if (error.value || reports.value.length === 0) return null;

  const reportsMap = new Map(reports.value.map((r) => [r.name, r]));

  const handleDownload = (name: string, filename: string) => {
    download({ name, filename, size: 0 });
  };

  const handleDownloadAll = () => {
    descargarTodos();
  };

  return (
    <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-2xl p-6 mb-6">
      <button
        type="button"
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
          <Boton
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
          </Boton>

          {REPORT_GROUPS.map((group) => {
            const groupReports = group.keys
              .map((k) => reportsMap.get(k))
              .filter((r): r is InfoReporte =>
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
                      type="button"
                      key={r.name}
                      onClick={() => handleDownload(r.name, r.filename)}
                      class="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm transition cursor-pointer border-none report-row"
                    >
                      <span class="truncate">
                        {ETIQUETAS_REPORTES[r.name] ?? r.name}
                      </span>
                      <span class="shrink-0 flex items-center gap-2">
                        <span class="text-xs text-[var(--text-muted)]">
                          {formatearTamano(r.size)}
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
