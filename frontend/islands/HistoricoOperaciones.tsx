import { useComputed, useSignal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import {
  getOperationsAnalytics,
  type OperationsHistoryItem,
} from "../services/api.ts";
import { darkSignal } from "../utils/theme.ts";
import { loadPlotly } from "../utils/plotly.ts";
import ErrorBox from "../components/ErrorBox.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";

const METRICS = [
  { key: "users_created", name: "Usuarios creados", color: "#00A859" },
  { key: "users_deleted", name: "Usuarios eliminados", color: "#CC1F24" },
  { key: "categories_created", name: "Categorías creadas", color: "#00D46A" },
  {
    key: "categories_deleted",
    name: "Categorías eliminadas",
    color: "#F05458",
  },
  { key: "courses_deleted", name: "Cursos eliminados", color: "#C01015" },
  { key: "total_errors", name: "Errores", color: "#F59E0B" },
];

function getRelevantKeys(entityType?: string, action?: string): string[] {
  if (entityType && action) {
    const target = `${entityType}_${action}`;
    const m = METRICS.find((m) => m.key === target);
    if (m) return [m.key, "total_errors"];
  }
  return METRICS.map((m) => m.key);
}

interface Props {
  entityType?: string;
  action?: string;
}

export default function HistoricoOperaciones({ entityType, action }: Props) {
  const data = useSignal<OperationsHistoryItem[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");
  const view = useSignal<"history" | "table">("history");
  const containerRef = useRef<HTMLDivElement>(null);
  const keys = useComputed(() => getRelevantKeys(entityType, action));

  useEffect(() => {
    (async () => {
      try {
        data.value = await getOperationsAnalytics(
          undefined,
          12,
          entityType,
          action,
        );
      } catch (e) {
        error.value = e instanceof Error
          ? e.message
          : "Error al cargar analítica";
      } finally {
        loading.value = false;
      }
    })();
  }, [entityType, action]);

  useEffect(() => {
    if (
      view.value !== "history" || !data.value.length || !containerRef.current
    ) return;
    let cancelled = false;

    (async () => {
      try {
        await loadPlotly();
        if (cancelled) return;

        const months = data.value.map((d) => d.month);
        const keys = getRelevantKeys(entityType, action);

        const traces = METRICS
          .filter((m) => keys.includes(m.key))
          .map((m) => ({
            name: m.name,
            x: months,
            y: data.value.map((d) =>
              (d as unknown as Record<string, number>)[m.key]
            ),
            type: "bar",
            marker: { color: m.color },
          }));

        const isDark = darkSignal.value;

        const layout = {
          barmode: "stack",
          autosize: true,
          margin: { t: 20, r: 20, b: 60, l: 50 },
          font: { color: isDark ? "#CDD6F4" : "#374151" },
          legend: { orientation: "h", y: 1.1, font: { size: 10 } },
          xaxis: { tickangle: -45, gridcolor: isDark ? "#313244" : "#E5E7EB" },
          yaxis: { gridcolor: isDark ? "#313244" : "#E5E7EB" },
          paper_bgcolor: isDark ? "#1E1E2E" : "#FFFFFF",
          plot_bgcolor: isDark ? "#1E1E2E" : "#FFFFFF",
        };

        if (containerRef.current) {
          window.Plotly.newPlot(containerRef.current, traces, layout, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ["sendDataToCloud"],
          });
        }
      } catch {
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML =
            `<div class="text-red-500 text-center p-4">Error al cargar gráfico</div>`;
        }
      }
    })();

    return () => {
      cancelled = true;
      if (containerRef.current) {
        try {
          window.Plotly?.purge(containerRef.current);
        } catch { /* ignore */ }
      }
    };
  }, [darkSignal.value, data.value, view.value]);

  const activeBtn = "bg-[var(--accent)] text-white";
  const inactiveBtn =
    "border bg-[var(--bg-primary)] border-[var(--border-secondary)] text-[var(--text-secondary)]";

  const relevant = METRICS.filter((m) => keys.value.includes(m.key));

  return (
    <div>
      <div class="flex gap-4 mb-6">
        {(["history", "table"] as const).map((v) => (
          <button
            type="button"
            key={v}
            onClick={() => (view.value = v)}
            class={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
              view.value === v ? activeBtn : inactiveBtn
            }`}
          >
            {v === "history" ? "Gráfico mensual" : "Tabla de datos"}
          </button>
        ))}
      </div>

      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
        {loading.value
          ? <LoadingSkeleton variant="chart" />
          : error.value
          ? <ErrorBox message={error.value} />
          : data.value.length === 0
          ? (
            <div class="text-center py-12 text-[var(--text-secondary)]">
              <p class="text-lg mb-2">Sin datos históricos de operaciones</p>
              <p class="text-sm">
                Una vez se ejecuten operaciones masivas (crear o eliminar
                usuarios, categorías, cursos), las métricas aparecerán aquí.
              </p>
            </div>
          )
          : view.value === "history"
          ? (
            <div
              ref={containerRef}
              style={{ width: "100%", height: "450px" }}
            />
          )
          : (
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-[var(--border-primary)]">
                    <th class="text-left py-2 px-2">Mes</th>
                    {relevant.map((m) => (
                      <th key={m.key} class="text-right py-2 px-2">{m.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.value.map((d) => (
                    <tr class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]">
                      <td class="py-2 px-2 font-medium">{d.month}</td>
                      {relevant.map((m) => (
                        <td
                          key={m.key}
                          class={`py-2 px-2 text-right ${
                            m.key === "total_errors"
                              ? "text-[var(--text-secondary)]"
                              : m.key.includes("deleted")
                              ? "text-[var(--brand-red)]"
                              : "text-[var(--brand-green)]"
                          }`}
                        >
                          {String(
                            (d as unknown as Record<string, unknown>)[m.key],
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>
    </div>
  );
}
