import { useSignal } from "@preact/signals";
import { useSubidaLote } from "../hooks/useSubidaLote.ts";
import { usePuertaSubida } from "../hooks/usePuertaSubida.ts";
import {
  cancelarLote,
  obtenerEstadoLote,
  pausarLote,
  reanudarLote,
  subirArchivoCsv,
} from "../services/api.ts";
import { IconoSpinner } from "../utils/iconos.tsx";
import CajaError from "../components/CajaError.tsx";
import BannerProcesoEnCurso from "../components/BannerProcesoEnCurso.tsx";
import TablaProgresoLote from "../components/TablaProgresoLote.tsx";
import AyudaConsulta, {
  type SeccionAyudaConsulta,
} from "../components/AyudaConsulta.tsx";
import SelectorArchivo from "../components/SelectorArchivo.tsx";

interface PropsSubirCsv {
  description: string;
  uploadEndpoint: string;
  etiquetaSingular: string;
  etiquetaPlural: string;
  action: "create" | "delete";
  help?: SeccionAyudaConsulta[];
}

export default function SubirCsv(
  {
    description,
    uploadEndpoint,
    etiquetaSingular,
    etiquetaPlural,
    action,
    help,
  }: PropsSubirCsv,
) {
  const detailOffset = useSignal(0);
  const PAGE_SIZE = 20;
  const { allowed, status, error: gateError } = usePuertaSubida(() => "");

  const {
    uploading,
    error,
    batchId,
    estadoLote,
    file,
    manejarCambioArchivo,
    manejarEnviar,
    iniciarSondeo,
  } = useSubidaLote({
    storageKey: `batch_${uploadEndpoint}`,
    doUpload: (f) => subirArchivoCsv(uploadEndpoint, f),
    onFetchStatus: (id) => obtenerEstadoLote(id, detailOffset.value, PAGE_SIZE),
    onUploadSuccess: () => {
      if (typeof window !== "undefined" && batchId.value) {
        window.location.href = `/operaciones/lotes/${batchId.value}`;
      }
    },
  });

  const handleDetailPageChange = (newOffset: number) => {
    detailOffset.value = newOffset;
    iniciarSondeo(batchId.value);
  };

  return (
    <div>
      {help && help.length > 0
        ? <AyudaConsulta sections={help} />
        : <p class="text-[var(--text-secondary)] text-sm mb-6">{description}
        </p>}

      <form
        onSubmit={manejarEnviar}
        class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 space-y-5"
      >
        <div>
          <SelectorArchivo
            id="csv-file"
            label="Archivo CSV"
            accept=".csv"
            file={file}
            onChange={manejarCambioArchivo}
            disabled={uploading.value || !allowed}
            onClear={() => {
              error.value = "";
            }}
          />
        </div>

        {!allowed && <BannerProcesoEnCurso status={status.value} />}
        {gateError.value && <CajaError message={gateError.value} />}
        {error.value && <CajaError message={error.value} />}

        <button
          type="submit"
          disabled={uploading.value || !allowed}
          class={`w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-[rgba(var(--brand-green-rgb),0.4)] transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2`}
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
            : `Subir y ${
              action === "create" ? "crear" : "eliminar"
            } ${etiquetaPlural}`}
        </button>
      </form>

      {estadoLote.value && (
        <TablaProgresoLote
          estadoLote={estadoLote.value}
          batchId={batchId.value}
          etiquetaSingular={etiquetaSingular}
          etiquetaPlural={etiquetaPlural}
          alPausar={() => pausarLote(batchId.value!)}
          alReanudar={() => reanudarLote(batchId.value!)}
          alCancelar={() => cancelarLote(batchId.value!)}
          pagination={{
            offset: detailOffset.value,
            tamanoPagina: PAGE_SIZE,
            alCambiarPagina: handleDetailPageChange,
          }}
        />
      )}
    </div>
  );
}
