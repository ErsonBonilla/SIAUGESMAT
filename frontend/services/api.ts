// services/api.ts — barrel (split: types, core, auth, jobs, analytics, reports, operations, queries)
export { BASE_URL } from "./api/core.ts";

export {
  login,
  getMyProfile,
} from "./api/auth.ts";

export {
  cancelExecution,
  getCurrentSemester,
  uploadFile,
  startProcess,
  resumeExecution,
  confirmExecution,
  pauseExecution,
  getExecution,
  listExecutions,
  getExecutionErrors,
  deleteExecution,
} from "./api/jobs.ts";

export {
  getHistory,
  getLatest,
  listCharts,
  getChartData,
} from "./api/analytics.ts";

export {
  listReports,
  downloadReport,
} from "./api/reports.ts";

export {
  uploadCsvFile,
  getBatchStatus,
  getBatchReportUrl,
  listBatches,
  getOperationsAnalytics,
} from "./api/operations.ts";

export {
  uploadVisibilityCsv,
} from "./api/mantenimiento.ts";

export {
  queryEntities,
  getQueryTaskStatus,
  getQueryExportUrl,
} from "./api/queries.ts";

export type {
  Execution,
  ErrorLog,
  SemesterMetrics,
  LatestExecution,
  UserProfile,
  ReportInfo,
  ReportsListResponse,
  ChartTracesLayout,
  ChartsListResponse,
  OperationBatchStatus,
  CsvUploadResponse,
  QueryTaskStatus,
  OperationBatchOut,
  OperationsHistoryItem,
} from "./api/types.ts";
