import { useSignal } from "@preact/signals";
import { useSubidaLote } from "../hooks/useSubidaLote.ts";
import { usePuertaSubida } from "../hooks/usePuertaSubida.ts";
import {
  cancelarLote,
  obtenerEstadoLote,
  pausarLote,
  reanudarLote,
  subirCsvVisibilidad,
} from "../services/api.ts";
import { IconoSpinner } from "../utils/iconos.tsx";
import CajaError from "../components/CajaError.tsx";
import BannerProcesoEnCurso from "../components/BannerProcesoEnCurso.tsx";
import SeccionHistorialOperaciones from "../components/SeccionHistorialOperaciones.tsx";
import TablaProgresoLote from "../components/TablaProgresoLote.tsx";
import BotonEjecucion from "../components/BotonEjecucion.tsx";
import AyudaConsulta from "../components/AyudaConsulta.tsx";
import SelectorArchivo from "../components/SelectorArchivo.tsx";

export default function IslandVisibilidadMasiva() {
  const visibility = useSignal<"show" | "hide">("show");
  const refreshKey = useSignal(0);
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
    storageKey: "batch_visibility",
    doUpload: (f) => subirCsvVisibilidad(f, visibility.value),
    onFetchStatus: (id) => obtenerEstadoLote(id, detailOffset.value, PAGE_SIZE),
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
    iniciarSondeo(id);
  };

  const handleDetailPageChange = (newOffset: number) => {
    detailOffset.value = newOffset;
    iniciarSondeo(batchId.value);
  };

  return (
    <div>
      <AyudaConsulta
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
        onSubmit={manejarEnviar}
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
            : `${visibility.value === "show" ? "Mostrar" : "Ocultar"} cursos`}
        </button>
      </form>

      {estadoLote.value && (
        <TablaProgresoLote
          estadoLote={estadoLote.value}
          batchId={batchId.value}
          etiquetaSingular="Curso"
          etiquetaPlural="cursos"
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

      <div class="mt-6">
        <SeccionHistorialOperaciones
          entityType="courses"
          action="visibility"
          idLoteActual={batchId.value}
          onSelectBatch={handleSelectBatch}
          disparadorActualizacion={refreshKey.value}
        />
      </div>

      <BotonEjecucion tab="visibilidad_cursos" />
    </div>
  );
}
