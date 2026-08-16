import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  consultarEntidades,
  type EstadoTareaConsulta,
  obtenerEstadoTareaConsulta,
} from "../services/api.ts";

const INTERVALO_SONDEO_MS = 2000;
const FALLOS_MAX = 5;

export function useConsultaTarea<T>(
  mapear: (resultado: unknown[]) => T[] = (r) => r as T[],
) {
  const data = useSignal<T[]>([]);
  const loading = useSignal(false);
  const error = useSignal("");
  const taskId = useSignal("");
  const taskStatus = useSignal<EstadoTareaConsulta | null>(null);
  const pollingId = useSignal<number | null>(null);

  const detenerSondeo = () => {
    if (pollingId.value) {
      clearInterval(pollingId.value);
      pollingId.value = null;
    }
  };

  const iniciarSondeo = (id: string) => {
    detenerSondeo();
    let fallosConsecutivos = 0;
    const tick = async () => {
      try {
        const status = await obtenerEstadoTareaConsulta(id);
        fallosConsecutivos = 0;
        taskStatus.value = status;
        if (status.status === "completed") {
          data.value = mapear(status.result || []);
          loading.value = false;
          detenerSondeo();
        } else if (status.status === "failed") {
          error.value = status.error || "Error desconocido al consultar.";
          loading.value = false;
          detenerSondeo();
        }
      } catch {
        fallosConsecutivos++;
        if (fallosConsecutivos >= FALLOS_MAX) {
          error.value = "La consulta dejó de responder. Reintentá más tarde.";
          loading.value = false;
          detenerSondeo();
        }
      }
    };
    tick();
    pollingId.value = setInterval(tick, INTERVALO_SONDEO_MS);
  };

  const iniciarConsulta = async (
    entity: string,
    params: Record<string, string>,
  ) => {
    loading.value = true;
    error.value = "";
    data.value = [];
    taskStatus.value = null;
    try {
      const result = await consultarEntidades(entity, params);
      taskId.value = result.task_id;
      iniciarSondeo(result.task_id);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al consultar.";
      loading.value = false;
    }
  };

  useEffect(() => {
    return detenerSondeo;
  }, []);

  return { data, loading, error, taskId, taskStatus, iniciarConsulta };
}
