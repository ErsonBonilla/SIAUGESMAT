export const MODALIDADES = ["PRESENCIAL", "DISTANCIA"] as const;
export type Modalidad = typeof MODALIDADES[number];

export const COLORES_SEMAFORO: Record<string, string> = {
  green: "var(--brand-green)",
  yellow: "#F59E0B",
  red: "var(--brand-red)",
  gray: "#9CA3AF",
};

export const COLORES_ESTADO: Record<string, string> = {
  completed: "status-green",
  running: "status-blue",
  queued: "status-yellow",
  pending: "status-yellow",
  paused: "status-blue",
  failed: "status-red",
  review_required: "status-orange",
  cancelled: "status-gray",
};

export const ETIQUETAS_ESTADO: Record<string, string> = {
  completed: "Completado",
  running: "En ejecución",
  queued: "Encolado",
  pending: "Pendiente",
  paused: "Pausado",
  failed: "Fallido",
  review_required: "Revisión requerida",
  cancelled: "Cancelado",
};

export const ETIQUETAS_MODO: Record<string, string> = {
  both: "Completo",
  courses: "Solo cursos",
  users: "Solo usuarios",
};

export const ETIQUETAS_MESES: Record<string, string> = {
  A: "Ene - Jun",
  B: "Jul - Dic",
};
