import { useComputed, useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import Layout from "../components/Layout.tsx";
import Card from "../components/Card.tsx";
import KpiCard from "../components/KpiCard.tsx";
import MiniBarChart from "../components/MiniBarChart.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";
import {
  type Execution,
  getHistory,
  getLatest,
  type LatestExecution,
  listExecutions,
  type SemesterMetrics,
} from "../services/api.ts";
import { profileSignal } from "../utils/profile.ts";
import { getTokenPayload } from "../utils/auth.ts";
import { SEMAPHORE_COLORS, STATUS_LABELS } from "../utils/constants.ts";
import {
  CheckIcon,
  ClockIcon,
  ExclamationIcon,
  MinusIcon,
  XMarkIcon,
} from "../utils/icons.tsx";

export default function DashboardIsland() {
  const historyData = useSignal<SemesterMetrics[]>([]);
  const latestExec = useSignal<LatestExecution | null>(null);
  const recentExecs = useSignal<Execution[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");

  useEffect(() => {
    loading.value = true;
    error.value = "";
    const rawModalidad = getTokenPayload()?.modalidad;
    const modalidad = typeof rawModalidad === "string"
      ? rawModalidad
      : undefined;
    const errors: string[] = [];
    Promise.all([
      getHistory(10, modalidad).catch((e) => {
        errors.push("Historial: " + (e instanceof Error ? e.message : "error"));
        return [] as SemesterMetrics[];
      }),
      getLatest(modalidad).catch((e) => {
        errors.push("Semáforo: " + (e instanceof Error ? e.message : "error"));
        return null;
      }),
      listExecutions({ limit: 5, modalidad }).catch((e) => {
        errors.push(
          "Ejecuciones: " + (e instanceof Error ? e.message : "error"),
        );
        return { total: 0, items: [] as Execution[] };
      }),
    ])
      .then(([history, latest, execs]) => {
        historyData.value = history;
        latestExec.value = latest;
        recentExecs.value = execs.items;
        if (errors.length) error.value = errors.join(" | ");
      })
      .catch((e) => {
        error.value = e instanceof Error ? e.message : "Error al cargar datos.";
      })
      .finally(() => {
        loading.value = false;
      });
  }, []);

  const displayName = profileSignal.value?.firstname || "Usuario";

  const kpis = useComputed(() => {
    const data = historyData.value;
    if (!data.length) return null;
    const totals = data.reduce(
      (acc, s) => ({
        ejecuciones: acc.ejecuciones + s.total_executions,
        cursos: acc.cursos + s.total_courses_created,
        matriculas: acc.matriculas + s.total_enrollments,
        errores: acc.errores + s.total_errors,
      }),
      { ejecuciones: 0, cursos: 0, matriculas: 0, errores: 0 },
    );
    const exito = totals.matriculas > 0
      ? ((totals.matriculas - totals.errores) / totals.matriculas * 100)
        .toFixed(1) + "%"
      : "—";
    const dur = data.length > 0
      ? Math.round(
        data.reduce((s, d) => s + d.avg_duration_seconds, 0) / data.length,
      ) + "s"
      : "—";
    return {
      ejecuciones: totals.ejecuciones,
      cursos: totals.cursos,
      matriculas: totals.matriculas,
      exito,
      duracion: dur,
    };
  });

  const chartData = useComputed(() =>
    historyData.value.slice(-6).map((s) => ({
      label: s.semester.replace(/(\d{4})([A-Z])/, "$1 $2"),
      value: s.total_executions,
    }))
  );

  const SemaphoreIcon = (s: string) => {
    switch (s) {
      case "green":
        return CheckIcon;
      case "yellow":
        return ExclamationIcon;
      case "red":
        return XMarkIcon;
      default:
        return MinusIcon;
    }
  };

  const renderBody = () => {
    if (loading.value) {
      return (
        <div class="space-y-6">
          <LoadingSkeleton variant="kpi" />
          <LoadingSkeleton variant="chart" />
        </div>
      );
    }

    if (error.value && !historyData.value.length) {
      return (
        <div class="flex items-center gap-1.5 text-xs text-[var(--brand-red)]">
          <span>{error.value}</span>
        </div>
      );
    }

    const noData = !historyData.value.length && !latestExec.value &&
      !recentExecs.value.length;

    if (noData) {
      return (
        <div class="text-center py-12 text-[var(--text-secondary)]">
          <p class="text-lg mb-2">Aún no hay datos</p>
          <p class="text-sm mb-4">
            Subí tu primer archivo para ver las métricas del dashboard.
          </p>
          <a
            href="/cursos/crear"
            class="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium border border-[var(--border-secondary)] bg-[var(--bg-primary)] text-[var(--text-primary)] no-underline cursor-pointer font-inherit leading-[1.4] hover:border-[var(--accent)] hover:bg-[var(--accent-bg-hover)] active:scale-[0.97] transition-all duration-150"
          >
            Subir archivo
          </a>
        </div>
      );
    }

    return (
      <div class="space-y-10">
        <hr class="border-0 h-px bg-[var(--border-secondary)] opacity-35 m-0" />
        <p class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-[0.06em]">
          Resumen
        </p>
        {kpis.value && (
          <div
            class="grid gap-5"
            style="grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))"
          >
            <KpiCard value={kpis.value.ejecuciones} label="Ejecuciones" />
            <KpiCard
              value={kpis.value.cursos.toLocaleString()}
              label="Cursos creados"
            />
            <KpiCard
              value={kpis.value.matriculas.toLocaleString()}
              label="Matrículas"
            />
            <KpiCard value={kpis.value.exito} label="Tasa éxito" />
            <KpiCard value={kpis.value.duracion} label="Duración prom." />
          </div>
        )}

        <hr class="border-0 h-px bg-[var(--border-secondary)] opacity-35 m-0" />
        <p class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-[0.06em]">
          Actividad
        </p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card padding="md">
            <p class="text-[0.8125rem] font-semibold text-[var(--text-secondary)] uppercase tracking-[0.04em] mb-3">
              Ejecuciones por semestre
            </p>
            {chartData.value.length > 0
              ? <MiniBarChart data={chartData.value} />
              : (
                <p class="text-sm text-[var(--text-secondary)]">
                  Sin datos históricos.
                </p>
              )}
          </Card>

          <Card padding="md">
            <p class="text-[0.8125rem] font-semibold text-[var(--text-secondary)] uppercase tracking-[0.04em] mb-3">
              Última ejecución
            </p>
            {latestExec.value
              ? (
                <div>
                  <div class="flex items-center gap-3 mb-3">
                    <div
                      class="flex items-center justify-center rounded-full"
                      style={{
                        width: "2.5rem",
                        height: "2.5rem",
                        backgroundColor:
                          SEMAPHORE_COLORS[latestExec.value.semaphore] ||
                          "var(--text-muted)",
                      }}
                    >
                      {(() => {
                        const Icon = SemaphoreIcon(latestExec.value.semaphore);
                        return (
                          <Icon
                            style={{
                              width: "1rem",
                              height: "1rem",
                              color: "#fff",
                            }}
                          />
                        );
                      })()}
                    </div>
                    <div>
                      <p class="font-semibold text-sm text-[var(--text-primary)]">
                        {latestExec.value.status === "completed"
                          ? (latestExec.value.semaphore === "green"
                            ? "Exitosa"
                            : latestExec.value.semaphore === "yellow"
                            ? "Advertencias"
                            : latestExec.value.semaphore === "red"
                            ? "Errores"
                            : "Sin datos")
                          : STATUS_LABELS[latestExec.value.status] ||
                            latestExec.value.status}
                      </p>
                      <p class="text-xs text-[var(--text-secondary)]">
                        {latestExec.value.semester}
                        {latestExec.value.error_rate !== undefined &&
                          ` · ${latestExec.value.error_rate.toFixed(1)}% error`}
                      </p>
                    </div>
                  </div>
                  <div class="flex items-center gap-3 text-xs text-[var(--text-secondary)] mb-3">
                    <span class="flex items-center gap-1">
                      <ClockIcon
                        style={{ width: "0.75rem", height: "0.75rem" }}
                      />
                      {latestExec.value.duration_seconds
                        ? Math.round(latestExec.value.duration_seconds) + "s"
                        : "—"}
                    </span>
                    <span>
                      {latestExec.value.errors_count} errores
                    </span>
                  </div>
                  <a
                    href={`/jobs/${latestExec.value.id}`}
                    class="text-xs font-medium no-underline text-[var(--accent)] hover:underline"
                  >
                    Ver detalle →
                  </a>
                </div>
              )
              : (
                <p class="text-sm text-[var(--text-secondary)]">
                  No hay ejecuciones recientes.
                </p>
              )}
          </Card>
        </div>

        <div>
          <p class="text-[0.8125rem] font-semibold text-[var(--text-secondary)] uppercase tracking-[0.04em] mb-3">
            Últimas ejecuciones
          </p>
          {recentExecs.value.length > 0
            ? (
              <Card padding="sm">
                <table class="w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      <th class="text-left px-4 py-3 font-semibold text-[0.6875rem] text-[var(--text-secondary)] uppercase tracking-[0.03em] border-b border-[var(--border-secondary)]">
                        Archivo
                      </th>
                      <th class="text-left px-4 py-3 font-semibold text-[0.6875rem] text-[var(--text-secondary)] uppercase tracking-[0.03em] border-b border-[var(--border-secondary)]">
                        Semestre
                      </th>
                      <th class="text-left px-4 py-3 font-semibold text-[0.6875rem] text-[var(--text-secondary)] uppercase tracking-[0.03em] border-b border-[var(--border-secondary)]">
                        Estado
                      </th>
                      <th class="text-left px-4 py-3 font-semibold text-[0.6875rem] text-[var(--text-secondary)] uppercase tracking-[0.03em] border-b border-[var(--border-secondary)]">
                        Errores
                      </th>
                      <th class="text-left px-4 py-3 font-semibold text-[0.6875rem] text-[var(--text-secondary)] uppercase tracking-[0.03em] border-b border-[var(--border-secondary)]">
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentExecs.value.map((ex) => {
                      const dotColor = ex.status === "completed"
                        ? "bg-green-500"
                        : ex.status === "failed"
                        ? "bg-[var(--brand-red)]"
                        : ex.status === "running" || ex.status === "pending"
                        ? "bg-[#F59E0B]"
                        : "bg-[var(--text-muted)]";
                      const label = ex.status === "completed"
                        ? "exitosa"
                        : ex.status === "failed"
                        ? "fallida"
                        : ex.status === "running"
                        ? "en proceso"
                        : ex.status === "pending"
                        ? "pendiente"
                        : ex.status;
                      return (
                        <tr key={ex.id}>
                          <td class="px-4 py-3 border-b border-[var(--border-secondary)] text-[var(--text-primary)] max-w-[160px] truncate">
                            {ex.filename}
                          </td>
                          <td class="px-4 py-3 border-b border-[var(--border-secondary)] text-[var(--text-primary)]">
                            {ex.semester}
                          </td>
                          <td class="px-4 py-3 border-b border-[var(--border-secondary)] text-[var(--text-primary)]">
                            <span class="flex items-center gap-1.5">
                              <span
                                class={`inline-block w-2 h-2 rounded-full shrink-0 ${dotColor}`}
                              />
                              {label}
                            </span>
                          </td>
                          <td class="px-4 py-3 border-b border-[var(--border-secondary)] text-[var(--text-primary)]">
                            {ex.errors_count}
                          </td>
                          <td class="px-4 py-3 border-b border-[var(--border-secondary)]">
                            <a
                              href={`/jobs/${ex.id}`}
                              class="text-xs text-[var(--accent)] no-underline font-medium hover:underline"
                            >
                              Detalle
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </Card>
            )
            : (
              <p class="text-sm text-[var(--text-secondary)]">
                Sin ejecuciones recientes.
              </p>
            )}
        </div>
      </div>
    );
  };

  return (
    <Layout title={`Bienvenido, ${displayName}`}>
      {renderBody()}
    </Layout>
  );
}
