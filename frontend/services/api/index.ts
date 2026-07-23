// services/api/index.ts — barrel re-export for backward compatibility
export { BASE_URL, authHeaders, handleResponse } from "./core.ts";
export type {
  Execution, ErrorLog, SemesterMetrics, SemaphoreStatus, LatestExecution, UserProfile,
  ReportInfo, ReportsListResponse, ChartInfo, ChartTracesLayout, ChartsListResponse,
  OperationBatchStatus, OperationItemOut, CsvUploadResponse, QueryTaskStatus,
  OperationBatchOut, OperationsHistoryItem,
} from "./types.ts";
export { login, getMyProfile } from "./auth.ts";
export {
  getCurrentSemester, uploadFile, startProcess, getExecution, listExecutions,
  getExecutionErrors, deleteExecution,
} from "./jobs.ts";
export { getHistory, getSemaphore, getLatest, listCharts, getChartData } from "./analytics.ts";
export { listReports, downloadReport } from "./reports.ts";
export {
  uploadCsvFile, getBatchStatus, getBatchReportUrl, listBatches, getOperationsAnalytics,
} from "./operations.ts";
export { queryEntities, getQueryTaskStatus, getQueryExportUrl } from "./queries.ts";
