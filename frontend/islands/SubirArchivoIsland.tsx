// islands/SubirArchivoIsland.tsx
import { useEffect } from "preact/hooks";
import { useSignal } from "@preact/signals";
import {
  iniciarProceso,
  obtenerSemestreActual,
  subirArchivo,
} from "../services/api.ts";
import { usePuertaSubida } from "../hooks/usePuertaSubida.ts";
import { IconoSpinner } from "../utils/iconos.tsx";
import CajaError from "../components/CajaError.tsx";
import BannerProcesoEnCurso from "../components/BannerProcesoEnCurso.tsx";
import SelectorArchivo from "../components/SelectorArchivo.tsx";

export default function SubidorArchivo() {
  const file = useSignal<File | null>(null);
  const semester = useSignal("");
  const modalidad = useSignal("DISTANCIA");

  const uploading = useSignal(false);
  const error = useSignal("");
  const successExecutionId = useSignal<number | null>(null);
  const semesterLoading = useSignal(true);

  const { allowed, status, error: gateError } = usePuertaSubida(() =>
    modalidad.value
  );

  useEffect(() => {
    obtenerSemestreActual()
      .then((s) => {
        semester.value = s;
        semesterLoading.value = false;
      })
      .catch(() => {
        semesterLoading.value = false;
      });
  }, []);

  const manejarCambioArchivo = (e: Event) => {
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

  const manejarEnviar = async (e: Event) => {
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
      const uploadResult = await subirArchivo(
        file.value,
        semester.value.toUpperCase(),
        modalidad.value,
      );
      const executionId = uploadResult.execution_id;
      await iniciarProceso(executionId);
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
      window.location.href = `/ejecuciones/${successExecutionId.value}`;
    }
  }, [successExecutionId.value]);

  if (successExecutionId.value) return null;

  return (
    <form
      onSubmit={manejarEnviar}
      class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 space-y-6"
    >
      {/* Archivo */}
      <div>
        <SelectorArchivo
          id="file"
          label="Archivo Excel"
          accept=".xlsx,.xls"
          file={file}
          onChange={manejarCambioArchivo}
          disabled={uploading.value || !allowed}
          onClear={() => {
            error.value = "";
          }}
        />
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
      {!allowed && <BannerProcesoEnCurso status={status.value} />}
      {gateError.value && <CajaError message={gateError.value} />}

      {/* Error */}
      {error.value && <CajaError message={error.value} />}

      {/* Botón de envío */}
      <button
        type="submit"
        disabled={uploading.value || !allowed}
        class="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {uploading.value
          ? (
            <>
              <IconoSpinner class="animate-spin h-5 w-5 text-white" />
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
