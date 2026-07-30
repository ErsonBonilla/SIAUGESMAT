// services/api.ts — barrel (split: types, core, auth, trabajos, analytics, reportes, operaciones, consultas)
export { authHeaders, BASE_URL, handleResponse } from "./api/core.ts";

export { getMyProfile, login } from "./api/auth.ts";

export {
  cancelExecution,
  confirmExecution,
  deleteExecution,
  getCurrentSemester,
  getExecution,
  getExecutionErrors,
  listExecutions,
  pauseExecution,
  resumeExecution,
  startProcess,
  uploadFile,
} from "./api/trabajos.ts";

export {
  getChartData,
  getHistory,
  getLatest,
  getSemaphore,
  listCharts,
} from "./api/analytics.ts";

export {
  downloadReport,
  getReportDownloadUrl,
  getReportFileUrl,
  listReports,
} from "./api/reportes.ts";

export {
  deleteBatch,
  getBatchReportUrl,
  getBatchStatus,
  getOperationsAnalytics,
  listBatches,
  pauseBatch,
  resumeBatch,
  uploadCsvFile,
} from "./api/operaciones.ts";

export { uploadVisibilityCsv } from "./api/mantenimiento.ts";

export {
  getQueryExportUrl,
  getQueryTaskStatus,
  queryEntities,
} from "./api/consultas.ts";

export type {
  BulkVisibilityResult,
  ChartInfo,
  ChartsListResponse,
  ChartTracesLayout,
  CsvUploadResponse,
  ErrorLog,
  Execution,
  LatestExecution,
  OperationBatchOut,
  OperationBatchStatus,
  OperationItemOut,
  OperationsHistoryItem,
  QueryTaskStatus,
  ReportInfo,
  ReportsListResponse,
  SemaphoreStatus,
  SemesterMetrics,
  UserProfile,
} from "./api/types.ts";
