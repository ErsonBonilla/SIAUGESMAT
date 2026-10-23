// services/api/tipos.ts

export interface Ejecucion {
  id: number;
  filename: string;
  semester: string;
  mode: string;
  status: string;
  metrics: Record<string, unknown> | null;
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

export interface RegistroError {
  id: number;
  execution_id: number;
  type: string;
  identifier: string | null;
  message: string | null;
  created_at: string;
}

export interface MetricasSemestre {
  semester: string;
  total_executions: number;
  total_courses_created: number;
  total_users_created: number;
  total_enrollments: number;
  total_errors: number;
  avg_duration_seconds: number;
  last_completed: string | null;
}

export interface EstadoSemaforo {
  semester: string;
  status: "green" | "yellow" | "red" | "gray";
  error_rate: number;
  avg_duration: number;
  message: string;
}

export interface EjecucionReciente {
  id: number;
  semester: string;
  filename: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  metrics: Record<string, unknown> | null;
  errors_count: number;
  error_rate: number;
  semaphore: string;
  moodle_version: string | null;
  modalidad: string | null;
}

export interface PerfilUsuario {
  username: string;
  firstname: string;
  lastname: string;
  profileimageurl: string;
}

export interface InfoReporte {
  name: string;
  filename: string;
  size: number;
}

export interface RespuestaListaReportes {
  execution_id: number;
  report_dir: string;
  reports: InfoReporte[];
}

export interface InfoGrafico {
  id: string;
  title: string;
  endpoint: string;
}

export interface DisposicionTrazasGrafico {
  traces: unknown[];
  layout: Record<string, unknown>;
}

export interface RespuestaListaGraficos {
  execution_id: number;
  moodle_version: string | null;
  modalidad: string | null;
  charts: InfoGrafico[];
}

export interface EstadoLoteOperacion {
  batch_id: string;
  entity_type: string;
  action: string;
  total: number;
  pending: number;
  processing: number;
  paused: number;
  completed: number;
  failed: number;
  cancelled: number;
  modalidad: string | null;
  created_at: string | null;
  completed_at: string | null;
  offset: number;
  limit: number;
  details: ItemOperacionSalida[];
}

export interface ItemOperacionSalida {
  identifier: string;
  status: string;
  error_message: string | null;
  attempt: number;
}

export interface RespuestaSubidaCsv {
  batch_id: string;
  entity_type: string;
  action: string;
  total: number;
  message: string;
}

export interface EstadoTareaConsulta {
  task_id: string;
  entity: string;
  status: string;
  total_count: number;
  result?: Record<string, unknown>[];
  error?: string;
}

export interface LoteOperacionSalida {
  batch_id: string;
  entity_type: string;
  action: string;
  total: number;
  completed: number;
  failed: number;
  paused: number;
  modalidad: string;
  created_at: string;
  completed_at: string | null;
}

export interface ItemHistorialOperaciones {
  month: string;
  users_created: number;
  users_deleted: number;
  categories_created: number;
  categories_deleted: number;
  courses_deleted: number;
  total_errors: number;
}

export interface FilaDocenteInactivo {
  teacher_name: string;
  username: string;
  email: string;
  course_name: string;
  course_shortname: string;
  program: string;
  cat: string;
  cat_prefix: string;
  last_access: number;
  days_since_last_access?: number;
}

export interface FilaCursoInactivo {
  id: string;
  shortname: string;
  fullname: string;
  categoryname: string;
  program: string;
  cat: string;
  cat_prefix: string;
  timecreated: number;
  timemodified: number;
  days_since_modified?: number;
}

export interface RespuestaDocentesInactivos {
  task_id: string;
  entity: string;
  status: string;
  total_count: number;
  result?: FilaDocenteInactivo[];
  error?: string;
}

export interface ItemNovedad {
  id: string;
  base_key: string;
  old_shortname: string;
  new_shortname: string;
  old_prof_cedula: string | null;
  new_prof_cedula: string | null;
  old_prof_name: string;
  new_prof_name: string;
  course_fullname: string;
  action: string;
  target_course_id: number | null;
}

export interface RespuestaNovedades {
  semester: string;
  previous_execution_id: number;
  previous_filename: string;
  total_compared: number;
  novedades: ItemNovedad[];
}
