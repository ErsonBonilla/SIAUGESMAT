import { useSignal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import {
  type EstadoLoteOperacion,
  obtenerEstadoLote,
} from "../services/api.ts";

interface OpcionesUsarSubidaLote {
  storageKey: string;
  doUpload: (file: File) => Promise<{ batch_id: string }>;
  onFetchStatus?: (id: string) => Promise<EstadoLoteOperacion>;
  onUploadSuccess?: () => void;
  onBatchComplete?: () => void;
}

const esCsv = (f: File) => f.name.toLowerCase().endsWith(".csv");

export function useSubidaLote({
  storageKey,
  doUpload,
  onFetchStatus,
  onUploadSuccess,
  onBatchComplete,
}: OpcionesUsarSubidaLote) {
  const file = useSignal<File | null>(null);
  const uploading = useSignal(false);
  const error = useSignal("");
  const pollingError = useSignal("");
  const batchId = useSignal("");
  const estadoLote = useSignal<EstadoLoteOperacion | null>(null);
  const pollingId = useSignal<ReturnType<typeof setInterval> | null>(null);

  const fnObtenerEstado = onFetchStatus ??
    ((id: string) => obtenerEstadoLote(id));
  const refIniciarSondeo = useRef<(id: string) => void>(() => {});
  const refAlCompletarLote = useRef(onBatchComplete);
  refAlCompletarLote.current = onBatchComplete;

  const iniciarSondeo = (id: string) => {
    if (pollingId.value) clearInterval(pollingId.value);
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(storageKey, id);
    }
    const tick = async () => {
      try {
        pollingError.value = "";
        const status = await fnObtenerEstado(id);
        estadoLote.value = status;
        if (status.pending === 0 && status.processing === 0) {
          if (pollingId.value) {
            clearInterval(pollingId.value);
            pollingId.value = null;
          }
          if (typeof sessionStorage !== "undefined") {
            sessionStorage.removeItem(storageKey);
          }
          refAlCompletarLote.current?.();
        }
      } catch {
        pollingError.value = "Error de conexión al consultar estado del lote";
      }
    };
    tick();
    pollingId.value = setInterval(tick, 2000);
  };

  refIniciarSondeo.current = iniciarSondeo;

  const manejarCambioArchivo = (e: Event) => {
    const target = e.target as HTMLInputElement;
    const f = target.files?.[0];
    if (f) {
      if (!esCsv(f)) {
        error.value = "Solo se permiten archivos CSV";
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
    pollingError.value = "";
    estadoLote.value = null;
    if (!file.value) {
      error.value = "Seleccione un archivo CSV.";
      return;
    }
    uploading.value = true;
    try {
      const result = await doUpload(file.value);
      batchId.value = result.batch_id;
      iniciarSondeo(result.batch_id);
      onUploadSuccess?.();
    } catch (err) {
      error.value = err instanceof Error
        ? err.message
        : "Error al subir el archivo.";
    } finally {
      uploading.value = false;
    }
  };

  useEffect(() => {
    if (typeof sessionStorage !== "undefined") {
      const saved = sessionStorage.getItem(storageKey);
      if (saved && !batchId.value) {
        batchId.value = saved;
        refIniciarSondeo.current(saved);
      }
    }
    return () => {
      if (pollingId.value) clearInterval(pollingId.value);
    };
  }, [storageKey]);

  return {
    file,
    uploading,
    error,
    pollingError,
    batchId,
    estadoLote,
    manejarCambioArchivo,
    manejarEnviar,
    iniciarSondeo,
  };
}
