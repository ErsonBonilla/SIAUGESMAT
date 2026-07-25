// services/api.ts — barrel (split: types, core, auth, jobs, analytics, reports, operations, queries)
export { BASE_URL } from "./api/core.ts";

export {
  login,
  getMyProfile,
} from "./api/auth.ts";

export {
  getCurrentSemester,
  uploadFile,
  startProcess,
  confirmExecution,
  pauseExecution,
  getExecution,
  listExecutions,
  getExecutionErrors,
  deleteExecution,
} from "./api/jobs.ts";

export {
  getHistory,
  getSemaphore,
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
  queryEntities,
  getQueryTaskStatus,
  getQueryExportUrl,
} from "./api/queries.ts";

export type {
  Execution,
  ErrorLog,
  SemesterMetrics,
  SemaphoreStatus,
  LatestExecution,
  UserProfile,
  ReportInfo,
  ReportsListResponse,
  ChartInfo,
  ChartTracesLayout,
  ChartsListResponse,
  OperationBatchStatus,
  OperationItemOut,
  CsvUploadResponse,
  QueryTaskStatus,
  OperationBatchOut,
  OperationsHistoryItem,
} from "./api/types.ts";
