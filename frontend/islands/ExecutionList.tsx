// islands/ExecutionList.tsx
import { useSignal, useComputed } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  cancelExecution,
  listExecutions,
  downloadReport,
  startProcess,
  resumeExecution,
  confirmExecution,
  pauseExecution,
  deleteExecution,
  BASE_URL,
  type Execution,
} from "../services/api.ts";
import { toast } from "../utils/toast.ts";
import { STATUS_COLORS, STATUS_LABELS, MODE_LABELS } from "../utils/constants.ts";
import ErrorBox from "../components/ErrorBox.tsx";
import Pagination from "../components/Pagination.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";

const PAGE_SIZE = 20;

export default function ExecutionList() {
  const items = useSignal<Execution[]>([]);
  const total = useSignal(0);
  const loading = useSignal(true);
  const error = useSignal("");
  const downloading = useSignal<number | null>(null);
  const processing = useSignal<number | null>(null);
  const deleting = useSignal<number | null>(null);
  const confirming = useSignal<number | null>(null);
  const pausing = useSignal<number | null>(null);
  const resuming = useSignal<number | null>(null);
  const cancelling = useSignal<number | null>(null);

  const filterSemester = useSignal("");
  const filterStatus = useSignal("");
  const filterMode = useSignal("");
  const offset = useSignal(0);

  const semesters = useSignal<string[]>([]);

  async function load() {
    loading.value = true;
    error.value = "";
    try {
      const result = await listExecutions({
        semester: filterSemester.value || undefined,
        status: filterStatus.value || undefined,
        mode: filterMode.value || undefined,
        limit: PAGE_SIZE,
        offset: offset.value,
      });
      items.value = result.items;
      total.value = result.total;

      const semSet = new Set<string>();
      for (const exec of result.items) {
        if (exec.semester) semSet.add(exec.semester);
      }
      semesters.value = [...semSet].sort().reverse();
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Error al cargar ejecuciones";
    } finally {
      loading.value = false;
    }
  }

  useEffect(() => {
    load();
  }, []);

  const totalPages = useComputed(() => Math.ceil(total.value / PAGE_SIZE));
  const currentPage = useComputed(() => Math.floor(offset.value / PAGE_SIZE) + 1);

  function applyFilters() {
    offset.value = 0;
    load();
  }

  async function handleDownloadZip(execId: number) {
    downloading.value = execId;
    try {
      await downloadReport(
        `${BASE_URL}/reports/${execId}/reports/download`,
        `reportes_ejecucion_${execId}.zip`,
      );
    } catch {
      toast("Error al descargar ZIP", "error");
    } finally {
      downloading.value = null;
    }
  }

  async function handleProcess(execId: number) {
    processing.value = execId;
    try {
      await startProcess(execId);
      toast("Procesamiento encolado correctamente", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al encolar procesamiento", "error");
    } finally {
      processing.value = null;
    }
  }

  async function handleDelete(execId: number) {
    if (!window.confirm("¿Eliminar esta ejecución y sus errores asociados?")) return;
    deleting.value = execId;
    try {
      await deleteExecution(execId);
      toast("Ejecución eliminada", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al eliminar la ejecución", "error");
    } finally {
      deleting.value = null;
    }
  }

  async function handleConfirm(execId: number) {
    if (!window.confirm("¿Confirmar la eliminación masiva de cursos? Esta acción continuará con el procesamiento.")) return;
    confirming.value = execId;
    try {
      await confirmExecution(execId);
      toast("Procesamiento reanudado con eliminación masiva confirmada", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al confirmar", "error");
    } finally {
      confirming.value = null;
    }
  }

  async function handlePause(execId: number) {
    pausing.value = execId;
    try {
      await pauseExecution(execId);
      toast("Ejecución pausada", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al pausar", "error");
    } finally {
      pausing.value = null;
    }
  }

  async function handleResume(execId: number) {
    resuming.value = execId;
    try {
      await resumeExecution(execId);
      toast("Ejecución reanudada", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al reanudar", "error");
    } finally {
      resuming.value = null;
    }
  }

  async function handleCancel(execId: number) {
    if (!window.confirm("¿Cancelar esta ejecución? Se detendrá el procesamiento en curso.")) return;
    cancelling.value = execId;
    try {
      await cancelExecution(execId);
      toast("Ejecución cancelada", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error al cancelar", "error");
    } finally {
      cancelling.value = null;
    }
  }

  function clearFilters() {
    filterSemester.value = "";
    filterStatus.value = "";
    filterMode.value = "";
    offset.value = 0;
    load();
  }

  const hasFilters = useComputed(() =>
    filterSemester.value || filterStatus.value || filterMode.value
  );

  return (
    <div>
      {/* Filtros */}
      <div class="flex flex-wrap gap-4 mb-8 items-end">
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Semestre</label>
          <select
            value={filterSemester.value}
            onChange={(e) => filterSemester.value = (e.target as HTMLSelectElement).value}
            class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
          >
            <option value="">Todos</option>
            {semesters.value.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Estado</label>
          <select
            value={filterStatus.value}
            onChange={(e) => filterStatus.value = (e.target as HTMLSelectElement).value}
            class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
          >
            <option value="">Todos</option>
            <option value="completed">Completado</option>
            <option value="running">En ejecución</option>
            <option value="pending">Pendiente</option>
            <option value="queued">Encolado</option>
            <option value="paused">Pausado</option>
            <option value="cancelled">Cancelado</option>
            <option value="failed">Fallido</option>
            <option value="review_required">Revisión requerida</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Modo</label>
          <select
            value={filterMode.value}
            onChange={(e) => filterMode.value = (e.target as HTMLSelectElement).value}
            class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
          >
            <option value="">Todos</option>
            <option value="both">Completo</option>
            <option value="courses">Solo cursos</option>
            <option value="users">Solo usuarios</option>
          </select>
        </div>
        <button
          onClick={applyFilters}
          class="px-4 py-1.5 bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white rounded text-sm hover:brightness-110"
        >
          Filtrar
        </button>
        {hasFilters.value && (
          <button
            onClick={clearFilters}
            class="px-4 py-1.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded text-sm hover:bg-[var(--border-secondary)]"
          >
            Limpiar
          </button>
        )}
      </div>

      {/* Tabla */}
      {loading.value ? (
        <LoadingSkeleton />
      ) : error.value ? (
        <ErrorBox message={error.value} />
      ) : items.value.length === 0 ? (
        <div class="text-center py-12 text-[var(--text-secondary)]">
          <p class="text-lg mb-2">No se encontraron ejecuciones</p>
          <p class="text-sm">Pruebe con otros filtros o suba un archivo desde el panel principal.</p>
        </div>
      ) : (
        <>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-primary)]">
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">#</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Archivo</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Semestre</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Modalidad</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Modo</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Estado</th>
                  <th class="text-right py-3 px-2 font-medium text-[var(--text-secondary)]">Acción</th>
                </tr>
              </thead>
              <tbody>
                {items.value.map((exec) => (
                  <tr class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]">
                    <td class="py-3 px-2 text-[var(--text-secondary)]">{exec.id}</td>
                    <td class="py-3 px-2 font-medium truncate max-w-[200px]">{exec.filename}</td>
                    <td class="py-3 px-2">{exec.semester}</td>
                    <td class="py-3 px-2">
                      {exec.modalidad
                        ? (
                          <span class="inline-flex items-center px-1.5 py-0.5 status-blue rounded text-xs font-medium">
                            {exec.modalidad}
                          </span>
                        )
                        : <span class="text-[var(--text-muted)]">—</span>}
                    </td>
                    <td class="py-3 px-2">{MODE_LABELS[exec.mode] || exec.mode}</td>
                    <td class="py-3 px-2">
                      <span
                        class={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          STATUS_COLORS[exec.status] || "status-gray"
                        }`}
                      >
                        {STATUS_LABELS[exec.status] || exec.status}
                      </span>
                    </td>
                    <td class="py-3 px-2 text-right whitespace-nowrap">
                      {exec.status === "completed" && (
                        <>
                          <button
                            onClick={() => handleDownloadZip(exec.id)}
                            disabled={downloading.value !== null}
                            class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-sm font-medium disabled:opacity-50"
                          >
                            {downloading.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  ZIP
                                </span>
                              )
                              : "ZIP"}
                          </button>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                        </>
                      )}
                      {exec.status === "completed" && (
                        <>
                          <a
                            href={`/reportes?execution_id=${exec.id}`}
                            class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-sm font-medium"
                          >
                            Reportes
                          </a>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                        </>
                      )}
                      <a
                        href={`/jobs/${exec.id}`}
                        class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-sm"
                      >
                        Detalle
                      </a>
                      {(exec.status === "pending" || exec.status === "queued" || exec.status === "failed" || exec.status === "review_required" || exec.status === "cancelled") && (
                        <>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                          <button
                            onClick={() => handleProcess(exec.id)}
                            disabled={processing.value !== null}
                            class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-sm font-medium disabled:opacity-50"
                          >
                            {processing.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  Encolando
                                </span>
                              )
                              : "Procesar"}
                          </button>
                        </>
                      )}
                      {(exec.status === "pending" || exec.status === "failed" || exec.status === "review_required" || exec.status === "cancelled" || exec.status === "queued") && (
                        <>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                          <button
                            onClick={() => handleDelete(exec.id)}
                            disabled={deleting.value !== null}
                            class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-sm font-medium disabled:opacity-50"
                          >
                            {deleting.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  Eliminando
                                </span>
                              )
                              : "Eliminar"}
                          </button>
                        </>
                      )}
                      {exec.status === "review_required" && (
                        <>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                          <button
                            onClick={() => handleConfirm(exec.id)}
                            disabled={confirming.value !== null}
                            class="text-[var(--brand-orange)] hover:text-[var(--brand-orange)] text-sm font-semibold disabled:opacity-50"
                          >
                            {confirming.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  Confirmando
                                </span>
                              )
                              : "Confirmar"}
                          </button>
                        </>
                      )}
                      {exec.status === "paused" && (
                        <>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                          <button
                            onClick={() => handleResume(exec.id)}
                            disabled={resuming.value !== null}
                            class="text-[var(--brand-orange)] hover:text-[var(--brand-orange)] text-sm font-semibold disabled:opacity-50"
                          >
                            {resuming.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  Reanudando
                                </span>
                              )
                              : "Reanudar"}
                          </button>
                        </>
                      )}
                      {exec.status === "running" && (
                        <>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                          <button
                            onClick={() => handlePause(exec.id)}
                            disabled={pausing.value !== null}
                            class="text-[var(--accent)] hover:text-[var(--accent)] text-sm font-medium disabled:opacity-50"
                          >
                            {pausing.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  Pausando
                                </span>
                              )
                              : "Pausar"}
                          </button>
                        </>
                      )}
                      {["running", "paused", "queued"].includes(exec.status) && (
                        <>
                          <span class="text-[var(--text-muted)] mx-1">|</span>
                          <button
                            onClick={() => handleCancel(exec.id)}
                            disabled={cancelling.value !== null}
                            class="text-red-500 hover:text-red-600 text-sm font-medium disabled:opacity-50"
                          >
                            {cancelling.value === exec.id
                              ? (
                                <span class="inline-flex items-center gap-1">
                                  <span class="w-3 h-3 border-2 border-[var(--text-muted)] border-t-transparent rounded-full animate-spin" />
                                  Cancelando
                                </span>
                              )
                              : "Cancelar"}
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            offset={offset.value}
            pageSize={PAGE_SIZE}
            total={total.value}
            label="ejecuciones"
            onPageChange={(o) => { offset.value = o; load(); }}
          />
        </>
      )}
    </div>
  );
}
