import { IconoCheck, IconoSpinner, IconoX } from "../utils/iconos.tsx";
import type { EstadoLoteOperacion } from "../services/api.ts";
import SeccionReportesLote from "./SeccionReportesLote.tsx";
import Paginacion from "./Paginacion.tsx";
import BarraProgreso from "./BarraProgreso.tsx";

interface PropsTablaProgresoLote {
  estadoLote: EstadoLoteOperacion;
  batchId: string;
  etiquetaSingular: string;
  etiquetaPlural: string;
  alPausar?: () => void;
  alReanudar?: () => void;
  alCancelar?: () => void;
  pagination?: {
    offset: number;
    tamanoPagina: number;
    alCambiarPagina: (offset: number) => void;
  };
}

export default function TablaProgresoLote(
  {
    estadoLote,
    batchId,
    etiquetaSingular,
    etiquetaPlural,
    alPausar,
    alReanudar,
    alCancelar,
    pagination,
  }: PropsTablaProgresoLote,
) {
  return (
    <div class="mt-6 bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
      <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
        Progreso del lote {batchId.slice(0, 8)}...
      </h3>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-5 mb-6">
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--text-primary)]">
            {estadoLote.total}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Total</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--brand-green)]">
            {estadoLote.completed}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Completados</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-[var(--brand-red)]">
            {estadoLote.failed}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Fallidos</div>
        </div>
        <div class="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div class="text-2xl font-bold text-yellow-600">
            {estadoLote.processing + estadoLote.pending}
          </div>
          <div class="text-xs text-[var(--text-secondary)]">Pendientes</div>
        </div>
      </div>

      {(() => {
        const total = estadoLote.total || 1;
        const done = estadoLote.completed + estadoLote.failed;
        const pct = Math.round(done / total * 100);
        const running = estadoLote.pending > 0 || estadoLote.processing > 0;
        return (
          <>
            <BarraProgreso
              faseActual={running
                ? `Procesando ${etiquetaPlural}...`
                : `${etiquetaSingular} procesados`}
              pasoActual={running ? 1 : 4}
              porcentajeProgreso={running ? pct : 100}
              status={running ? "running" : "completed"}
            />
            {!running && (
              <div class="mt-4">
                <SeccionReportesLote batchId={batchId} />
                <a
                  href={`/operaciones/lotes/${batchId}`}
                  class="mt-3 inline-block text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] no-underline"
                >
                  Ver detalle completo →
                </a>
              </div>
            )}
          </>
        );
      })()}

      {(estadoLote.pending > 0 || estadoLote.processing > 0 ||
        estadoLote.paused > 0) && (
        <div class="flex justify-end gap-2 mt-3">
          {(estadoLote.pending > 0 || estadoLote.processing > 0) && alPausar &&
            (
              <button
                type="button"
                onClick={alPausar}
                class="px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-400 hover:bg-amber-500 text-white transition"
              >
                ⏸ Pausa
              </button>
            )}
          {estadoLote.paused > 0 && alReanudar && (
            <button
              type="button"
              onClick={alReanudar}
              class="px-3 py-1.5 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-700 text-white transition"
            >
              ▶ Reanudar
            </button>
          )}
          {alCancelar && (
            <button
              type="button"
              onClick={alCancelar}
              class="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition"
            >
              ✖ Cancelar
            </button>
          )}
        </div>
      )}

      <div class="mt-6 overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--border-primary)]">
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                {etiquetaSingular}
              </th>
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                Estado
              </th>
              <th class="text-left py-2 px-2 font-medium text-[var(--text-secondary)]">
                Error
              </th>
            </tr>
          </thead>
          <tbody>
            {estadoLote.details.map((d) => (
              <tr
                key={d.identifier}
                class="border-b border-[var(--border-primary)]"
              >
                <td class="py-2 px-2 font-medium text-[var(--text-primary)]">
                  {d.identifier}
                </td>
                <td class="py-2 px-2">
                  {d.status === "completed" && (
                    <span class="flex items-center gap-1 text-[var(--brand-green)]">
                      <IconoCheck class="w-3 h-3" />Completado
                    </span>
                  )}
                  {d.status === "failed" && (
                    <span class="flex items-center gap-1 text-[var(--brand-red)]">
                      <IconoX class="w-3 h-3" />Fallido
                    </span>
                  )}
                  {d.status === "processing" && (
                    <span class="flex items-center gap-1 text-yellow-600">
                      <IconoSpinner class="animate-spin w-3 h-3" />Procesando
                    </span>
                  )}
                  {d.status === "pending" && (
                    <span class="text-[var(--text-muted)]">Pendiente</span>
                  )}
                </td>
                <td class="py-2 px-2 text-xs text-[var(--text-muted)] whitespace-nowrap">
                  {d.error_message || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pagination && (
        <Paginacion
          offset={pagination.offset}
          tamanoPagina={pagination.tamanoPagina}
          total={estadoLote.total}
          label="registros"
          alCambiarPagina={pagination.alCambiarPagina}
        />
      )}
    </div>
  );
}
