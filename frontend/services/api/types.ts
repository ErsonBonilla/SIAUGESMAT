// services/api/types.ts

export interface Execution {
  id: number;
  filename: string;
  semester: string;
  mode: string;
  status: string;
  metrics: Record<string, number> | null;
  errors_count: number;
  current_phase?: string | null;
  progress_pct?: number | null;
  progress_updated_at?: string | null;
  current_step?: number | null;
  eta_seconds?: number | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  modalidad: string | null;
  moodle_version?: string | null;
  report_dir?: string | null;
  celery_task_id?: string | null;
  created_at: string;
}

export interface ErrorLog {
  id: number;
  execution_id: number;
  type: string;
  identifier: string | null;
  message: string | null;
  created_at: string;
}

export interface SemesterMetrics {
  semester: string;
  total_executions: number;
  total_courses_created: number;
  total_users_created: number;
  total_enrollments: number;
  total_errors: number;
  avg_duration_seconds: number;
  last_completed: string | null;
}

export interface SemaphoreStatus {
  semester: string;
  status: "green" | "yellow" | "red" | "gray";
  error_rate: number;
  avg_duration: number;
  message: string;
}

export interface LatestExecution extends Execution {
  error_rate: number;
  semaphore: string;
  modalidad: string | null;
}

export interface UserProfile {
  username: string;
  firstname: string;
  lastname: string;
  profileimageurl: string;
}

export interface ReportInfo {
  name: string;
  filename: string;
  size: number;
}

export interface ReportsListResponse {
  execution_id: number;
  report_dir: string;
  reports: ReportInfo[];
}

export interface ChartInfo {
  id: string;
  title: string;
  endpoint: string;
}

export interface ChartTracesLayout {
  traces: unknown[];
  layout: Record<string, unknown>;
}

export interface ChartsListResponse {
  execution_id: number;
  modalidad: string | null;
  charts: ChartInfo[];
}

export interface OperationBatchStatus {
  batch_id: string;
  entity_type: string;
  action: string;
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  offset: number;
  limit: number;
  details: OperationItemOut[];
}

export interface OperationItemOut {
  identifier: string;
  status: string;
  error_message: string | null;
  attempt: number;
}

export interface CsvUploadResponse {
  batch_id: string;
  entity_type: string;
  action: string;
  total: number;
  message: string;
}

export interface QueryTaskStatus {
  task_id: string;
  entity: string;
  status: string;
  total_count: number;
  result?: Record<string, unknown>[];
  error?: string;
}

export interface OperationBatchOut {
  batch_id: string;
  entity_type: string;
  action: string;
  total: number;
  completed: number;
  failed: number;
  modalidad: string;
  created_at: string;
  completed_at: string | null;
}

export interface OperationsHistoryItem {
  month: string;
  users_created: number;
  users_deleted: number;
  categories_created: number;
  categories_deleted: number;
  courses_deleted: number;
  total_errors: number;
}

export interface BulkVisibilityResult {
  updated: number;
  failed: number;
  not_found: number;
  duration_seconds: number;
}
