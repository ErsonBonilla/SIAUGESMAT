// islands/FileUploader.tsx
import { useEffect } from "preact/hooks";
import { useSignal } from "@preact/signals";
import {
  getCurrentSemester,
  startProcess,
  uploadFile,
} from "../services/api.ts";
import { useUploadGate } from "../hooks/useUploadGate.ts";
import { SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import ProcessInProgressBanner from "../components/ProcessInProgressBanner.tsx";

export default function FileUploader() {
  const file = useSignal<File | null>(null);
  const semester = useSignal("");
  const modalidad = useSignal("DISTANCIA");

  const uploading = useSignal(false);
  const error = useSignal("");
  const successExecutionId = useSignal<number | null>(null);
  const semesterLoading = useSignal(true);

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

  const handleSubmit = async (e: Event) => {
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

    uploading.value = true;
    try {
      const uploadResult = await uploadFile(
        file.value,
        semester.value.toUpperCase(),
        modalidad.value,
      );
      const executionId = uploadResult.execution_id;
      await startProcess(executionId);
      successExecutionId.value = executionId;
    } catch (err) {
      error.value = err instanceof Error
        ? err.message
        : "Error al subir el archivo.";
    } finally {
      uploading.value = false;
    }
  };

  useEffect(() => {
    if (successExecutionId.value && typeof window !== "undefined") {
      window.location.href = `/jobs/${successExecutionId.value}`;
    }
  }, [successExecutionId.value]);

  if (successExecutionId.value) return null;

  return (
    <form
      onSubmit={handleSubmit}
      class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 space-y-6"
    >
      {/* Archivo */}
      <div>
        <label
          for="file"
          class="block text-sm font-medium text-[var(--text-secondary)] mb-2"
        >
          Archivo Excel
        </label>
        <div class="flex items-center gap-4">
          <input
            id="file"
            type="file"
            accept=".xlsx,.xls"
            onChange={handleFileChange}
            disabled={uploading.value || !allowed}
            class="block w-full text-sm text-[var(--text-muted)] file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[var(--file-btn-bg)] file:text-[var(--file-btn-text)] hover:file:bg-[var(--file-btn-hover)] transition disabled:opacity-40 disabled:cursor-not-allowed"
          />
        </div>
      </div>

      {/* Semestre */}
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

      <input type="hidden" name="modalidad" value={modalidad.value} />

      {/* Proceso en curso: no se pueden subir archivos */}
      {!allowed && <ProcessInProgressBanner status={status.value} />}
      {gateError.value && <ErrorBox message={gateError.value} />}

      {/* Error */}
      {error.value && <ErrorBox message={error.value} />}

      {/* Botón de envío */}
      <button
        type="submit"
        disabled={uploading.value || !allowed}
        class="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {uploading.value
          ? (
            <>
              <SpinnerIcon class="animate-spin h-5 w-5 text-white" />
              <span>Subiendo y encolando...</span>
            </>
          )
          : !allowed
          ? "Esperando a que finalice el proceso en curso"
          : "Subir y procesar archivo"}
      </button>
    </form>
  );
}
