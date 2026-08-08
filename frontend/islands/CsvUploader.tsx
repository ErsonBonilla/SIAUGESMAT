import { useSignal } from "@preact/signals";
import { useBatchUpload } from "../hooks/useBatchUpload.ts";
import { useUploadGate } from "../hooks/useUploadGate.ts";
import {
  cancelBatch,
  getBatchStatus,
  pauseBatch,
  resumeBatch,
  uploadCsvFile,
} from "../services/api.ts";
import { SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import ProcessInProgressBanner from "../components/ProcessInProgressBanner.tsx";
import BatchProgressTable from "../components/BatchProgressTable.tsx";
import QueryHelp, { type QueryHelpSection } from "../components/QueryHelp.tsx";
import FilePicker from "../components/FilePicker.tsx";

interface CsvUploaderProps {
  description: string;
  uploadEndpoint: string;
  labelSingular: string;
  labelPlural: string;
  action: "create" | "delete";
  help?: QueryHelpSection[];
}

export default function CsvUploader(
  {
    description,
    uploadEndpoint,
    labelSingular,
    labelPlural,
    action,
    help,
  }: CsvUploaderProps,
) {
  const detailOffset = useSignal(0);
  const PAGE_SIZE = 20;
  const { allowed, status, error: gateError } = useUploadGate(() => "");

  const {
    uploading,
    error,
    batchId,
    batchStatus,
    file,
    handleFileChange,
    handleSubmit,
    startPolling,
  } = useBatchUpload({
    storageKey: `batch_${uploadEndpoint}`,
    doUpload: (f) => uploadCsvFile(uploadEndpoint, f),
    onFetchStatus: (id) => getBatchStatus(id, detailOffset.value, PAGE_SIZE),
    onUploadSuccess: () => {
      if (typeof window !== "undefined" && batchId.value) {
        window.location.href = `/operaciones/lotes/${batchId.value}`;
      }
    },
  });

  const handleDetailPageChange = (newOffset: number) => {
    detailOffset.value = newOffset;
    startPolling(batchId.value);
  };

  return (
    <div>
      {help && help.length > 0
        ? <QueryHelp sections={help} />
        : <p class="text-[var(--text-secondary)] text-sm mb-6">{description}
        </p>}

      <form
        onSubmit={handleSubmit}
        class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 space-y-5"
      >
        <div>
          <FilePicker
            id="csv-file"
            label="Archivo CSV"
            accept=".csv"
            file={file}
            onChange={handleFileChange}
            disabled={uploading.value || !allowed}
            onClear={() => {
              error.value = "";
            }}
          />
        </div>

        {!allowed && <ProcessInProgressBanner status={status.value} />}
        {gateError.value && <ErrorBox message={gateError.value} />}
        {error.value && <ErrorBox message={error.value} />}

        <button
          type="submit"
          disabled={uploading.value || !allowed}
          class={`w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2`}
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
            : `Subir y ${
              action === "create" ? "crear" : "eliminar"
            } ${labelPlural}`}
        </button>
      </form>

      {batchStatus.value && (
        <BatchProgressTable
          batchStatus={batchStatus.value}
          batchId={batchId.value}
          labelSingular={labelSingular}
          labelPlural={labelPlural}
          onPause={() => pauseBatch(batchId.value!)}
          onResume={() => resumeBatch(batchId.value!)}
          onCancel={() => cancelBatch(batchId.value!)}
          pagination={{
            offset: detailOffset.value,
            pageSize: PAGE_SIZE,
            onPageChange: handleDetailPageChange,
          }}
        />
      )}
    </div>
  );
}
