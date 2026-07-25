export const MODALIDADES = ["PRESENCIAL", "DISTANCIA"] as const;
export type Modalidad = typeof MODALIDADES[number];

export const SEMAPHORE_COLORS: Record<string, string> = {
  green: "var(--brand-green)",
  yellow: "#F59E0B",
  red: "var(--brand-red)",
  gray: "#9CA3AF",
};

export const SEMAPHORE_TEXTS: Record<string, string> = {
  green: "Ejecución exitosa",
  yellow: "Advertencias",
  red: "Errores críticos",
  gray: "Sin ejecuciones",
};

export const STATUS_COLORS: Record<string, string> = {
  completed: "status-green",
  running: "status-blue",
  queued: "status-yellow",
  pending: "status-yellow",
  paused: "status-blue",
  failed: "status-red",
  review_required: "status-orange",
  cancelled: "status-gray",
};

export const STATUS_LABELS: Record<string, string> = {
  completed: "Completado",
  running: "En ejecución",
  queued: "Encolado",
  pending: "Pendiente",
  paused: "Pausado",
  failed: "Fallido",
  review_required: "Revisión requerida",
  cancelled: "Cancelado",
};

export const MODE_LABELS: Record<string, string> = {
  both: "Completo",
  courses: "Solo cursos",
  users: "Solo usuarios",
};
