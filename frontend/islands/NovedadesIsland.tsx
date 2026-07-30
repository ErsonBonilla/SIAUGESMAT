import { useEffect } from "preact/hooks";
import { useSignal, useComputed } from "@preact/signals";
import { getCurrentSemester } from "../services/api.ts";
import { compareNovedades, applyNovedades } from "../services/api/novedades.ts";
import type { NovedadItem } from "../services/api/types.ts";
import { SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";

type Step = "upload" | "results" | "applying" | "done";

export default function NovedadesIsland() {
  const step = useSignal<Step>("upload");
  const file = useSignal<File | null>(null);
  const semester = useSignal("");
  const modalidad = useSignal("DISTANCIA");
  const loading = useSignal(false);
  const applying = useSignal(false);
  const error = useSignal("");
  const semesterLoading = useSignal(true);

  const previousFilename = useSignal("");
  const totalCompared = useSignal(0);
  const novedades = useSignal<NovedadItem[]>([]);
  const selectedIds = useSignal<Set<string>>(new Set());
  const applyResults = useSignal<Array<{ id: string; success: boolean; message: string }>>([]);

  useEffect(() => {
    getCurrentSemester()
      .then((s) => {
        semester.value = s;
        semesterLoading.value = false;
      })
      .catch(() => {
        semesterLoading.value = false;
      });
  }, []);

  const handleFileChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    const f = target.files?.[0];
    if (f) {
      if (!f.name.toLowerCase().endsWith(".xlsx")) {
        error.value = "Solo se permiten archivos .xlsx";
        file.value = null;
        return;
      }
      file.value = f;
      error.value = "";
    }
  };

  const handleCompare = async (e: Event) => {
    e.preventDefault();
    error.value = "";
    if (!file.value) {
      error.value = "Seleccione un archivo Excel (.xlsx).";
      return;
    }
    loading.value = true;
    try {
      const result = await compareNovedades(
        file.value,
        semester.value.toUpperCase(),
        modalidad.value,
      );
      previousFilename.value = result.previous_filename;
      totalCompared.value = result.total_compared;
      novedades.value = result.novedades;
      selectedIds.value = new Set(result.novedades.map((n) => n.id));
      step.value = "results";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al comparar.";
    } finally {
      loading.value = false;
    }
  };

  const toggleAll = () => {
    if (selectedIds.value.size === novedades.value.length) {
      selectedIds.value = new Set();
    } else {
      selectedIds.value = new Set(novedades.value.map((n) => n.id));
    }
  };

  const toggleOne = (id: string) => {
    const next = new Set(selectedIds.value);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedIds.value = next;
  };

  const selectedCount = useComputed(() => selectedIds.value.size);
  const anySelected = useComputed(() => selectedIds.value.size > 0);

  const handleApply = async () => {
    if (!anySelected.value) return;
    applying.value = true;
    error.value = "";
    step.value = "applying";

    const selected = novedades.value.filter((n) => selectedIds.value.has(n.id));
    try {
      const result = await applyNovedades(semester.value, selected.map((n) => ({
        id: n.id,
        action: n.action,
        old_shortname: n.old_shortname,
        new_shortname: n.new_shortname,
        course_fullname: n.course_fullname,
        new_prof_username: "",
        new_prof_cedula: n.new_prof_cedula || "",
      })));
      applyResults.value = result.results.map((r) => ({
        id: r.novedad_id,
        success: r.success,
        message: r.message,
      }));
      step.value = "done";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al aplicar.";
      step.value = "results";
    } finally {
      applying.value = false;
    }
  };

  if (step.value === "applying") {
    return (
      <div class="max-w-3xl mx-auto text-center py-12">
        <SpinnerIcon class="animate-spin h-10 w-10 mx-auto text-[var(--accent)]" />
        <p class="mt-4 text-[var(--text-secondary)]">Aplicando novedades...</p>
      </div>
    );
  }

  return (
    <div class="max-w-5xl mx-auto space-y-6">
      {/* Upload step */}
      {(step.value === "upload" || step.value === "results") && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
          <h2 class="text-lg font-semibold mb-4 text-[var(--text-primary)]">
            Subir nueva carga académica
          </h2>
          <form onSubmit={handleCompare} class="space-y-4">
            <div>
              <label
                for="file"
                class="block text-sm font-medium text-[var(--text-secondary)] mb-2"
              >
                Archivo Excel (.xlsx)
              </label>
              <input
                id="file"
                type="file"
                accept=".xlsx"
                onChange={handleFileChange}
                disabled={loading.value}
                class="block w-full text-sm text-[var(--text-muted)] file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[var(--file-btn-bg)] file:text-[var(--file-btn-text)] hover:file:bg-[var(--file-btn-hover)] transition disabled:opacity-50"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Semestre
              </label>
              {semesterLoading.value
                ? <span class="text-sm text-[var(--text-muted)]">Cargando...</span>
                : (
                  <div class="px-4 py-2.5 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-secondary)] text-[var(--text-primary)] font-medium text-sm inline-block">
                    {semester.value}
                  </div>
                )}
            </div>

            {error.value && <ErrorBox message={error.value} />}

            <button
              type="submit"
              disabled={loading.value}
              class="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading.value
                ? (
                  <>
                    <SpinnerIcon class="animate-spin h-5 w-5 text-white" />
                    <span>Comparando...</span>
                  </>
                )
                : "Comparar con carga anterior"}
            </button>
          </form>
        </div>
      )}

      {/* Results table */}
      {step.value === "results" && novedades.value.length > 0 && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">
              Novedades detectadas: {novedades.value.length}
            </h2>
            <span class="text-sm text-[var(--text-muted)]">
              Carga anterior: {previousFilename.value} &middot; {totalCompared.value} cursos comparados
            </span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-primary)]">
                  <th class="text-left py-2 pr-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.value.size === novedades.value.length}
                      onClick={toggleAll}
                      class="accent-[var(--accent)]"
                    />
                  </th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">Curso</th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">Profesor anterior</th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">Nuevo profesor</th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">Acción</th>
                </tr>
              </thead>
              <tbody>
                {novedades.value.map((n) => (
                  <tr class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-secondary)]/50">
                    <td class="py-2 pr-2">
                      <input
                        type="checkbox"
                        checked={selectedIds.value.has(n.id)}
                        onClick={() => toggleOne(n.id)}
                        class="accent-[var(--accent)]"
                      />
                    </td>
                    <td class="py-2 px-2">
                      <div class="font-medium text-[var(--text-primary)]">{n.course_fullname || n.base_key}</div>
                      <div class="text-xs text-[var(--text-muted)] font-mono">{n.old_shortname}</div>
                    </td>
                    <td class="py-2 px-2 text-[var(--text-secondary)]">
                      {n.old_prof_name || n.old_prof_cedula || <span class="italic">Sin asignar</span>}
                    </td>
                    <td class="py-2 px-2 text-[var(--text-secondary)]">
                      {n.new_prof_name || n.new_prof_cedula || "—"}
                    </td>
                    <td class="py-2 px-2">
                      {n.action === "hide_and_create"
                        ? (
                          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">
                            Ocultar + Crear
                          </span>
                        )
                        : (
                          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                            Rehabilitar
                          </span>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {error.value && <div class="mt-4"><ErrorBox message={error.value} /></div>}

          <div class="mt-6 flex items-center justify-end gap-3">
            <a
              href="/cursos/crear"
              class="py-2 px-4 rounded-lg border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition text-sm font-medium"
            >
              Cancelar
            </a>
            <button
              onClick={handleApply}
              disabled={!anySelected.value || applying.value}
              class="py-2.5 px-6 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Aplicar seleccionados ({selectedCount.value})
            </button>
          </div>
        </div>
      )}

      {step.value === "results" && novedades.value.length === 0 && !loading.value && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-12 text-center">
          <div class="text-4xl mb-3">✓</div>
          <h2 class="text-lg font-semibold text-[var(--text-primary)] mb-2">
            No se detectaron novedades
          </h2>
          <p class="text-[var(--text-secondary)] text-sm">
            Los cursos de la nueva carga coinciden con los de la carga anterior.
          </p>
          <a
            href="/cursos/crear"
            class="mt-4 inline-block py-2 px-4 rounded-lg border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition text-sm font-medium"
          >
            Volver a crear cursos
          </a>
        </div>
      )}

      {/* Done step */}
      {step.value === "done" && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
          <h2 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
            Resultados de la aplicación
          </h2>
          <div class="space-y-3">
            {applyResults.value.map((r) => {
              const nov = novedades.value.find((n) => n.id === r.id);
              return (
                <div class={`p-3 rounded-lg border ${
                  r.success
                    ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20"
                    : "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20"
                }`}>
                  <div class="flex items-center justify-between">
                    <div>
                      <span class="font-medium text-[var(--text-primary)]">
                        {nov?.course_fullname || nov?.base_key || r.id}
                      </span>
                      <span class="text-xs text-[var(--text-muted)] ml-2 font-mono">
                        {nov?.old_shortname}
                      </span>
                    </div>
                    <span class={`text-sm font-medium ${
                      r.success ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"
                    }`}>
                      {r.success ? "✓ Aplicado" : "✗ Error"}
                    </span>
                  </div>
                  {r.message && (
                    <p class="text-xs text-[var(--text-muted)] mt-1">{r.message}</p>
                  )}
                </div>
              );
            })}
          </div>
          <div class="mt-6 flex items-center justify-between">
            <span class="text-sm text-[var(--text-secondary)]">
              {applyResults.value.filter((r) => r.success).length} de {applyResults.value.length} aplicadas correctamente
            </span>
            <a
              href="/cursos/crear"
              class="py-2.5 px-6 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 transition"
            >
              Volver a crear cursos
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
