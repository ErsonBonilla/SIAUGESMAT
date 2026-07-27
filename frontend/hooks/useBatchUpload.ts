import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { getBatchStatus, type OperationBatchStatus } from "../services/api.ts";

interface UseBatchUploadOptions {
  storageKey: string;
  doUpload: (file: File) => Promise<{ batch_id: string }>;
  onFetchStatus?: (id: string) => Promise<OperationBatchStatus>;
  onUploadSuccess?: () => void;
  onBatchComplete?: () => void;
}

const isCsv = (f: File) => f.name.toLowerCase().endsWith(".csv");

export function useBatchUpload({
  storageKey,
  doUpload,
  onFetchStatus,
  onUploadSuccess,
  onBatchComplete,
}: UseBatchUploadOptions) {
  const file = useSignal<File | null>(null);
  const uploading = useSignal(false);
  const error = useSignal("");
  const batchId = useSignal("");
  const batchStatus = useSignal<OperationBatchStatus | null>(null);
  const pollingId = useSignal<number | null>(null);

  const fetchStatusFn = onFetchStatus ?? ((id: string) => getBatchStatus(id));

  const startPolling = (id: string) => {
    if (pollingId.value) clearInterval(pollingId.value);
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(storageKey, id);
    }
    const tick = async () => {
      try {
        const status = await fetchStatusFn(id);
        batchStatus.value = status;
        if (status.pending === 0 && status.processing === 0) {
          if (pollingId.value) {
            clearInterval(pollingId.value);
            pollingId.value = null;
          }
          if (typeof sessionStorage !== "undefined") {
            sessionStorage.removeItem(storageKey);
          }
          onBatchComplete?.();
        }
      } catch {
        // ignorar errores de polling
      }
    };
    tick();
    pollingId.value = setInterval(tick, 2000);
  };

  const handleFileChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    const f = target.files?.[0];
    if (f) {
      if (!isCsv(f)) {
        error.value = "Solo se permiten archivos CSV";
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
    if (!file.value) {
      error.value = "Seleccione un archivo CSV.";
      return;
    }
    uploading.value = true;
    try {
      const result = await doUpload(file.value);
      batchId.value = result.batch_id;
      startPolling(result.batch_id);
      onUploadSuccess?.();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al subir el archivo.";
    } finally {
      uploading.value = false;
    }
  };

  useEffect(() => {
    if (typeof sessionStorage !== "undefined") {
      const saved = sessionStorage.getItem(storageKey);
      if (saved && !batchId.value) {
        batchId.value = saved;
        startPolling(saved);
      }
    }
    return () => {
      if (pollingId.value) clearInterval(pollingId.value);
    };
  }, []);

  return {
    file,
    uploading,
    error,
    batchId,
    batchStatus,
    handleFileChange,
    handleSubmit,
    startPolling,
  };
}
