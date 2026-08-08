import { useEffect } from "preact/hooks";
import { useSignal } from "@preact/signals";
import { compareNovedades, getCurrentSemester } from "../services/api.ts";
import { useUploadGate } from "../hooks/useUploadGate.ts";
import type { NovedadItem } from "../services/api.ts";
import { DownloadIcon, SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import ProcessInProgressBanner from "../components/ProcessInProgressBanner.tsx";
import QueryHelp from "../components/QueryHelp.tsx";
import FilePicker from "../components/FilePicker.tsx";

type Step = "upload" | "results";

function _rowsToCsv(items: NovedadItem[]): string {
  const headers = [
    "tipo",
    "cat",
    "programa",
    "base_key",
    "curso",
    "shortname_anterior",
    "shortname_nuevo",
    "profesor_anterior",
    "profesor_nuevo",
    "cedula_anterior",
    "cedula_nueva",
  ];
  const rows = items.map((n) => {
    const parts = n.base_key.split("_");
    return [
      n.action,
      parts[0] || "",
      parts[1] || "",
      n.base_key,
      n.course_fullname,
      n.old_shortname,
      n.new_shortname,
      n.old_prof_name || n.old_prof_cedula || "",
      n.new_prof_name || n.new_prof_cedula || "",
      n.old_prof_cedula || "",
      n.new_prof_cedula || "",
    ].map((v) => `"${v}"`);
  });
  return "\uFEFF" + headers.join(",") + "\n" +
    rows.map((r) => r.join(",")).join("\n");
}

function downloadCsv(items: NovedadItem[], filename: string) {
  if (items.length === 0) return;
  const csv = _rowsToCsv(items);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function NovedadesIsland() {
  const step = useSignal<Step>("upload");
  const file = useSignal<File | null>(null);
  const semester = useSignal("");
  const modalidad = useSignal("DISTANCIA");
  const loading = useSignal(false);
  const error = useSignal("");
  const semesterLoading = useSignal(true);

  const previousFilename = useSignal("");
  const totalCompared = useSignal(0);
  const novedades = useSignal<NovedadItem[]>([]);

  const { allowed, status, error: gateError } = useUploadGate(() =>
    modalidad.value
  );

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
      if (
        !f.name.toLowerCase().endsWith(".xlsx") &&
        !f.name.toLowerCase().endsWith(".xls")
      ) {
        error.value = "Solo se permiten archivos .xlsx o .xls";
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
    if (!allowed) {
      error.value =
        "No se pueden subir archivos mientras haya un proceso en ejecución.";
      return;
    }
    if (!file.value) {
      error.value = "Seleccione un archivo Excel (.xlsx o .xls).";
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
      step.value = "results";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al comparar.";
    } finally {
      loading.value = false;
    }
  };

  return (
    <div class="max-w-5xl mx-auto space-y-6">
      <QueryHelp
        sections={[
          {
            title: "Qué hace esta comparación",
            body:
              "Compara la nueva carga académica (Excel) con la carga anterior del mismo semestre almacenada en Moodle, y detecta los cambios de asignación docente.",
          },
          {
            title: "Pasos",
            body: [
              "1. Seleccione el archivo Excel (.xlsx o .xls) de la nueva carga académica.",
              "2. Verifique el semestre (se detecta automáticamente según la fecha del servidor).",
              '3. Presione "Comparar con carga anterior".',
            ],
          },
          {
            title: "Tipos de novedades",
            body: [
              "Cambio de profesor: el curso cambia de docente asignado.",
              "Curso eliminado: el curso ya no aparece en la nueva carga.",
              "Curso nuevo: el curso no existía en la carga anterior.",
            ],
          },
        ]}
      />
      {/* Upload step */}
      {(step.value === "upload" || step.value === "results") && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
          <h2 class="text-lg font-semibold mb-4 text-[var(--text-primary)]">
            Subir nueva carga académica
          </h2>
          <form onSubmit={handleCompare} class="space-y-4">
            <div>
              <FilePicker
                id="file"
                label="Archivo Excel (.xlsx o .xls)"
                accept=".xlsx,.xls"
                file={file}
                onChange={handleFileChange}
                disabled={loading.value || !allowed}
                onClear={() => {
                  error.value = "";
                }}
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Semestre
              </label>
              {semesterLoading.value
                ? (
                  <span class="text-sm text-[var(--text-muted)]">
                    Cargando...
                  </span>
                )
                : (
                  <div class="px-4 py-2.5 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-secondary)] text-[var(--text-primary)] font-medium text-sm inline-block">
                    {semester.value}
                  </div>
                )}
            </div>

            {!allowed && <ProcessInProgressBanner status={status.value} />}
            {gateError.value && <ErrorBox message={gateError.value} />}
            {error.value && <ErrorBox message={error.value} />}

            <button
              type="submit"
              disabled={loading.value || !allowed}
              class="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading.value
                ? (
                  <>
                    <SpinnerIcon class="animate-spin h-5 w-5 text-white" />
                    <span>Comparando...</span>
                  </>
                )
                : !allowed
                ? "Esperando a que finalice el proceso en curso"
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
              Carga anterior: {previousFilename.value} &middot;{" "}
              {totalCompared.value} cursos comparados
            </span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-primary)]">
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">
                    Tipo
                  </th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">
                    CAT
                  </th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">
                    Programa
                  </th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">
                    Curso
                  </th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">
                    Profesor anterior
                  </th>
                  <th class="text-left py-2 px-2 text-[var(--text-secondary)] font-medium">
                    Nuevo profesor
                  </th>
                </tr>
              </thead>
              <tbody>
                {novedades.value.map((n) => {
                  const parts = n.base_key.split("_");
                  return (
                    <tr class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-secondary)]/50">
                      <td class="py-2 px-2">
                        <span
                          class={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                            n.action === "cambio_profesor"
                              ? "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300"
                              : n.action === "curso_eliminado"
                              ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                              : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                          }`}
                        >
                          {n.action === "cambio_profesor"
                            ? "Cambio profesor"
                            : n.action === "curso_eliminado"
                            ? "Eliminado"
                            : "Nuevo"}
                        </span>
                      </td>
                      <td class="py-2 px-2 text-[var(--text-primary)] font-mono text-xs">
                        {parts[0] || "—"}
                      </td>
                      <td class="py-2 px-2 text-[var(--text-primary)] font-mono text-xs">
                        {parts[1] || "—"}
                      </td>
                      <td class="py-2 px-2">
                        <div class="font-medium text-[var(--text-primary)] text-sm">
                          {n.course_fullname || n.base_key}
                        </div>
                        <div class="text-xs text-[var(--text-muted)] font-mono">
                          {n.old_shortname || n.new_shortname}
                        </div>
                      </td>
                      <td class="py-2 px-2 text-[var(--text-secondary)] text-sm">
                        {n.old_prof_name || n.old_prof_cedula || (
                          <span class="italic text-xs">—</span>
                        )}
                      </td>
                      <td class="py-2 px-2 text-[var(--text-secondary)] text-sm">
                        {n.new_prof_name || n.new_prof_cedula || (
                          <span class="italic text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {error.value && (
            <div class="mt-4">
              <ErrorBox message={error.value} />
            </div>
          )}

          <div class="mt-6 flex items-center justify-end gap-3">
            <a
              href="/cursos/crear"
              class="py-2 px-4 rounded-lg border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition text-sm font-medium"
            >
              Volver
            </a>
            <div class="flex gap-2">
              {novedades.value.filter((n) => n.action === "curso_eliminado")
                    .length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    downloadCsv(
                      novedades.value.filter((n) =>
                        n.action === "curso_eliminado"
                      ),
                      `eliminados_${new Date().toISOString().slice(0, 10)}.csv`,
                    )}
                  class="inline-flex items-center gap-2 py-2.5 px-4 rounded-lg border border-red-400 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 text-sm font-medium transition"
                >
                  <DownloadIcon class="w-4 h-4" />
                  Solo eliminados ({novedades.value.filter((n) =>
                    n.action === "curso_eliminado"
                  ).length})
                </button>
              )}
              <button
                type="button"
                onClick={() =>
                  downloadCsv(
                    novedades.value,
                    `novedades_${new Date().toISOString().slice(0, 10)}.csv`,
                  )}
                class="inline-flex items-center gap-2 py-2.5 px-6 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 transition"
              >
                <DownloadIcon class="w-4 h-4" />
                Descargar CSV
              </button>
            </div>
          </div>
        </div>
      )}

      {step.value === "results" && novedades.value.length === 0 &&
        !loading.value && (
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
    </div>
  );
}
