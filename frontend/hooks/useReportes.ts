// hooks/useReportes.ts
import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  descargarReporte,
  type InfoReporte,
  listarReportes,
  obtenerUrlArchivoReporte,
  obtenerUrlDescargaReporte,
} from "../services/api.ts";

interface OpcionesUsarReportes {
  executionId: number;
}

export function useReportes({ executionId }: OpcionesUsarReportes) {
  const reports = useSignal<InfoReporte[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");

  useEffect(() => {
    loading.value = true;
    listarReportes(executionId)
      .then((data) => {
        reports.value = data.reports;
      })
      .catch((e) => {
        error.value = e instanceof Error
          ? e.message
          : "Error al cargar reportes.";
      })
      .finally(() => {
        loading.value = false;
      });
  }, [executionId]);

  function download(report: InfoReporte) {
    descargarReporte(
      obtenerUrlArchivoReporte(executionId, report.name),
      report.filename,
    );
  }

  function descargarTodos() {
    descargarReporte(
      obtenerUrlDescargaReporte(executionId),
      `reportes_ejecucion_${executionId}.zip`,
    );
  }

  return { reports, loading, error, download, descargarTodos };
}
