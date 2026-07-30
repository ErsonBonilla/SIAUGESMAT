// services/api.ts — barrel (split: types, core, auth, trabajos, analytics, reportes, operaciones, consultas)
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
  cancelBatch,
  deleteBatch,
  getBatchReportFileUrl,
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

export { compareNovedades } from "./api/novedades.ts";

export type {
  ChartInfo,
  ChartsListResponse,
  ChartTracesLayout,
  CsvUploadResponse,
  ErrorLog,
  Execution,
  InactiveTeacherRow,
  LatestExecution,
  NovedadItem,
  NovedadesResponse,
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
