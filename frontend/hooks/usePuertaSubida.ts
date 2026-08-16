// hooks/usePuertaSubida.ts
import { useEffect, useRef } from "preact/hooks";
import { useSignal } from "@preact/signals";
import { type EstadoSubida, obtenerEstadoSubida } from "../services/api.ts";

/**
 * Indica si se permite subir archivos para una modalidad mientras no haya
 * un proceso en ejecución (ETL o lote CSV). Consulta el backend al montar
 * y hace polling mientras haya un proceso activo para que la interfaz se
 * desbloquee sola cuando este finalice.
 */
export function usePuertaSubida(modalidad: () => string) {
  const status = useSignal<EstadoSubida | null>(null);
  const checking = useSignal(true);
  const error = useSignal("");

  const modalidadRef = useRef(modalidad);
  modalidadRef.current = modalidad;

  useEffect(() => {
    let stopped = false;
    let intervalId: number | null = null;

    const check = async () => {
      try {
        const st = await obtenerEstadoSubida(modalidadRef.current());
        if (stopped) return;
        status.value = st;
        error.value = "";
        if (st.allowed) {
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }
        } else if (intervalId === null) {
          intervalId = setInterval(check, 3000);
        }
      } catch (e) {
        if (stopped) return;
        error.value = e instanceof Error
          ? e.message
          : "Error al consultar estado";
      } finally {
        checking.value = false;
      }
    };

    check();
    return () => {
      stopped = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  const allowed = status.value?.allowed ?? true;

  return {
    allowed,
    status,
    checking,
    error,
  };
}
