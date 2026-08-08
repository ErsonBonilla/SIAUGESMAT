import { useSignal } from "@preact/signals";
import { useBatchUpload } from "../hooks/useBatchUpload.ts";
import { useUploadGate } from "../hooks/useUploadGate.ts";
import {
  cancelBatch,
  getBatchStatus,
  pauseBatch,
  resumeBatch,
  uploadVisibilityCsv,
} from "../services/api.ts";
import { SpinnerIcon } from "../utils/icons.tsx";
import ErrorBox from "../components/ErrorBox.tsx";
import ProcessInProgressBanner from "../components/ProcessInProgressBanner.tsx";
import OperationHistorySection from "../components/OperationHistorySection.tsx";
import BatchProgressTable from "../components/BatchProgressTable.tsx";
import ExecutionButton from "../components/ExecutionButton.tsx";
import QueryHelp from "../components/QueryHelp.tsx";
import FilePicker from "../components/FilePicker.tsx";

export default function BulkVisibilityIsland() {
  const visibility = useSignal<"show" | "hide">("show");
  const refreshKey = useSignal(0);
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
    storageKey: "batch_visibility",
    doUpload: (f) => uploadVisibilityCsv(f, visibility.value),
    onFetchStatus: (id) => getBatchStatus(id, detailOffset.value, PAGE_SIZE),
    onUploadSuccess: () => {
      refreshKey.value++;
      if (typeof window !== "undefined" && batchId.value) {
        window.location.href = `/operaciones/lotes/${batchId.value}`;
      }
    },
    onBatchComplete: () => {
      refreshKey.value++;
    },
  });

  const handleSelectBatch = (id: string) => {
    batchId.value = id;
    detailOffset.value = 0;
    startPolling(id);
  };

  const handleDetailPageChange = (newOffset: number) => {
    detailOffset.value = newOffset;
    startPolling(batchId.value);
  };

  return (
    <div>
      <QueryHelp
        sections={[
          {
            title: "Archivo CSV requerido",
            body:
              "Suba un archivo CSV con la columna shortname conteniendo los códigos cortos de los cursos a mostrar u ocultar.",
          },
          {
            title: "Acción",
            body: [
              "Mostrar: pone el curso visible en Moodle (visible = 1).",
              "Ocultar: oculta el curso en Moodle (visible = 0).",
            ],
          },
          {
            title: "Procesamiento",
            body:
              "El archivo se procesa como un lote: puede pausar, reanudar o cancelar desde la tabla de progreso.",
          },
        ]}
      />

      <form
        onSubmit={handleSubmit}
        class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 space-y-5"
      >
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-3">
            Acción
          </label>
          <div class="flex gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="visibility"
                value="show"
                checked={visibility.value === "show"}
                onChange={() => visibility.value = "show"}
                class="text-[var(--brand-green)] focus:ring-[var(--brand-green)]"
              />
              <span class="text-sm text-[var(--text-primary)]">
                <span class="text-[var(--brand-green)] font-medium">
                  Mostrar
                </span>{" "}
                (visible = 1)
              </span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="visibility"
                value="hide"
                checked={visibility.value === "hide"}
                onChange={() => visibility.value = "hide"}
                class="text-[var(--brand-red)] focus:ring-[var(--brand-red)]"
              />
              <span class="text-sm text-[var(--text-primary)]">
                <span class="text-[var(--brand-red)] font-medium">Ocultar</span>
                {" "}
                (visible = 0)
              </span>
            </label>
          </div>
        </div>

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
            : `${visibility.value === "show" ? "Mostrar" : "Ocultar"} cursos`}
        </button>
      </form>

      {batchStatus.value && (
        <BatchProgressTable
          batchStatus={batchStatus.value}
          batchId={batchId.value}
          labelSingular="Curso"
          labelPlural="cursos"
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

      <div class="mt-6">
        <OperationHistorySection
          entityType="courses"
          action="visibility"
          currentBatchId={batchId.value}
          onSelectBatch={handleSelectBatch}
          refreshTrigger={refreshKey.value}
        />
      </div>

      <ExecutionButton tab="visibilidad_cursos" />
    </div>
  );
}
