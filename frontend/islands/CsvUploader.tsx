import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { uploadCsvFile, getBatchStatus, type OperationBatchStatus } from "../services/api.ts";
import { SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import BatchProgressTable from "../components/BatchProgressTable.tsx";

interface CsvUploaderProps {
  title: string;
  description: string;
  uploadEndpoint: string;
  labelSingular: string;
  labelPlural: string;
  action: "create" | "delete";
}

export default function CsvUploader({ title, description, uploadEndpoint, labelSingular, labelPlural, action }: CsvUploaderProps) {
  const file = useSignal<File | null>(null);
  const uploading = useSignal(false);
  const error = useSignal("");
  const batchId = useSignal("");
  const batchStatus = useSignal<OperationBatchStatus | null>(null);
  const pollingId = useSignal<number | null>(null);

  const handleFileChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    const f = target.files?.[0];
    if (f) {
      if (!f.name.toLowerCase().endsWith(".csv")) {
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
      const result = await uploadCsvFile(uploadEndpoint, file.value);
      batchId.value = result.batch_id;
      startPolling(result.batch_id);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al subir el archivo.";
    } finally {
      uploading.value = false;
    }
  };

  const startPolling = (id: string) => {
    if (pollingId.value) clearInterval(pollingId.value);
    const fetchStatus = async () => {
      try {
        const status = await getBatchStatus(id);
        batchStatus.value = status;
        if (status.pending === 0 && status.processing === 0) {
          if (pollingId.value) {
            clearInterval(pollingId.value);
            pollingId.value = null;
          }
        }
      } catch {
        //
      }
    };
    fetchStatus();
    pollingId.value = setInterval(fetchStatus, 2000);
  };

  useEffect(() => {
    return () => {
      if (pollingId.value) clearInterval(pollingId.value);
    };
  }, []);

  return (
    <div>
      <p class="text-[var(--text-secondary)] text-sm mb-6">{description}</p>

      <form onSubmit={handleSubmit} class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 space-y-5">
        <div>
          <label for="csv-file" class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
            Archivo CSV
          </label>
          <input
            id="csv-file"
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            disabled={uploading.value}
            class="block w-full text-sm text-[var(--text-muted)] file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[var(--file-btn-bg)] file:text-[var(--file-btn-text)] hover:file:bg-[var(--file-btn-hover)] transition disabled:opacity-50"
          />
        </div>

        {error.value && (
          <ErrorBox message={error.value} />
        )}

        <button
          type="submit"
          disabled={uploading.value}
          class={`w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2`}
        >
          {uploading.value ? (
            <>
              <SpinnerIcon class="animate-spin h-5 w-5 text-white" />
              <span>Subiendo y encolando...</span>
            </>
          ) : (
            `Subir y ${action === "create" ? "crear" : "eliminar"} ${labelPlural}`
          )}
        </button>
      </form>

      {batchStatus.value && (
        <BatchProgressTable
          batchStatus={batchStatus.value}
          batchId={batchId.value}
          labelSingular={labelSingular}
          labelPlural={labelPlural}
        />
      )}
    </div>
  );
}
