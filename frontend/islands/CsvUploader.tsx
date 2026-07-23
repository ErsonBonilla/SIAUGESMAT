import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { uploadCsvFile, getBatchStatus, getBatchReportUrl, type OperationBatchStatus } from "../services/api.ts";
import { ExclamationCircleIcon, SpinnerIcon, CheckIcon, XMarkIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";

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
        <div class="mt-6 bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
          <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">Progreso del lote {batchId.value.slice(0, 8)}...</h3>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-5 mb-6">
            <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
              <div class="text-2xl font-bold text-[var(--text-primary)]">{batchStatus.value.total}</div>
              <div class="text-xs text-[var(--text-secondary)]">Total</div>
            </div>
            <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
              <div class="text-2xl font-bold text-[var(--brand-green)]">{batchStatus.value.completed}</div>
              <div class="text-xs text-[var(--text-secondary)]">Completados</div>
            </div>
            <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
              <div class="text-2xl font-bold text-[var(--brand-red)]">{batchStatus.value.failed}</div>
              <div class="text-xs text-[var(--text-secondary)]">Fallidos</div>
            </div>
            <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
              <div class="text-2xl font-bold text-yellow-600">{batchStatus.value.processing + batchStatus.value.pending}</div>
              <div class="text-xs text-[var(--text-secondary)]">Pendientes</div>
            </div>
          </div>

          {batchStatus.value.pending > 0 || batchStatus.value.processing > 0 ? (
            <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <SpinnerIcon class="animate-spin h-4 w-4" />
              <span>Procesando {labelPlural}...</span>
            </div>
          ) : (
            <div class="flex flex-col sm:flex-row sm:items-center gap-3">
              <div class="flex items-center gap-2 text-sm text-[var(--brand-green)]">
                <CheckIcon class="w-4 h-4" />
                <span>Procesamiento completado</span>
              </div>
              <a
                href={getBatchReportUrl(batchId.value)}
                download
                class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white text-sm font-medium no-underline hover:brightness-110 transition"
              >
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" class="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Descargar reportes (CSV)</span>
              </a>
            </div>
          )}

          <div class="mt-6 overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-primary)]">
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">{labelSingular}</th>
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">Estado</th>
                  <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">Error</th>
                </tr>
              </thead>
              <tbody>
                {batchStatus.value.details.map((d) => (
                  <tr key={d.identifier} class="border-b border-[var(--border-primary)]">
                    <td class="py-2 px-2 font-medium text-[var(--text-primary)]">{d.identifier}</td>
                    <td class="py-2 px-2">
                      {d.status === "completed" && <span class="flex items-center gap-1 text-[var(--brand-green)]"><CheckIcon class="w-3 h-3" />Completado</span>}
                      {d.status === "failed" && <span class="flex items-center gap-1 text-[var(--brand-red)]"><XMarkIcon class="w-3 h-3" />Fallido</span>}
                      {d.status === "processing" && <span class="flex items-center gap-1 text-yellow-600"><SpinnerIcon class="animate-spin w-3 h-3" />Procesando</span>}
                      {d.status === "pending" && <span class="text-[var(--text-muted)]">Pendiente</span>}
                    </td>
                    <td class="py-2 px-2 text-xs text-[var(--text-muted)] max-w-[200px] truncate">{d.error_message || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
