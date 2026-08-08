// hooks/useReports.ts
import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import {
  downloadReport,
  getReportDownloadUrl,
  getReportFileUrl,
  listReports,
  type ReportInfo,
} from "../services/api.ts";

interface UseReportsOptions {
  executionId: number;
}

export function useReports({ executionId }: UseReportsOptions) {
  const reports = useSignal<ReportInfo[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");

  useEffect(() => {
    loading.value = true;
    listReports(executionId)
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

  function download(report: ReportInfo) {
    downloadReport(getReportFileUrl(executionId, report.name), report.filename);
  }

  function downloadAll() {
    downloadReport(
      getReportDownloadUrl(executionId),
      `reportes_ejecucion_${executionId}.zip`,
    );
  }

  return { reports, loading, error, download, downloadAll };
}
