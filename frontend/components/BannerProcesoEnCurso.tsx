// components/BannerProcesoEnCurso.tsx
import type { EstadoSubida } from "../services/api.ts";
import { ETIQUETAS_ESTADO } from "../utils/constantes.ts";
import {
  etiquetaAccionLote,
  etiquetaEntidadLote,
} from "../utils/etiquetas-lote.ts";

interface Props {
  status: EstadoSubida | null;
}

/**
 * Aviso mostrado cuando hay un proceso en ejecución que impide subir
 * nuevos archivos hasta que finalice.
 */
export default function BannerProcesoEnCurso({ status }: Props) {
  if (!status || status.allowed) return null;

  const what = status.execution
    ? `la ejecución "${status.execution.filename}" (${
      ETIQUETAS_ESTADO[status.execution.status] ?? status.execution.status
    })`
    : status.batch
    ? `el lote de ${
      etiquetaEntidadLote(status.batch.entity_type).toLowerCase()
    } (${etiquetaAccionLote(status.batch.action).toLowerCase()})`
    : "un proceso";

  return (
    <div
      class="flex items-start gap-2.5 rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-700 dark:text-yellow-300"
      role="status"
    >
      <span aria-hidden="true">⏳</span>
      <span>
        Hay un proceso en curso ({what}). No se pueden subir archivos hasta que
        el proceso en ejecución finalice.
      </span>
    </div>
  );
}
