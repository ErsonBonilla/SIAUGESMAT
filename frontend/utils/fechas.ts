import { format, formatDistanceToNow, isValid, parseISO } from "date-fns";
import { es } from "date-fns/locale";

function formatearIsoConPatron(
  isoString: string | null | undefined,
  patron: string,
): string {
  if (!isoString) return "—";
  try {
    const date = parseISO(isoString);
    if (!isValid(date)) return "Fecha inválida";
    return format(date, patron, { locale: es });
  } catch {
    return "Fecha inválida";
  }
}

/**
 * Formatea una fecha ISO a un formato legible en español.
 * Ejemplo: "15/03/2025 14:30"
 */
export function formatearFechaHora(
  isoString: string | null | undefined,
): string {
  return formatearIsoConPatron(isoString, "dd/MM/yyyy HH:mm");
}

/**
 * Formatea una fecha ISO a solo fecha (sin hora).
 * Ejemplo: "15/03/2025"
 */
export function formatearFecha(isoString: string | null | undefined): string {
  return formatearIsoConPatron(isoString, "dd/MM/yyyy");
}

/**
 * Formatea un timestamp Unix (segundos) a fecha o fecha+hora local.
 */
export function formatearTimestampUnix(
  ts: number | null | undefined,
  conHora = false,
): string {
  if (!ts || !Number.isFinite(ts) || ts <= 0) return "Nunca";
  const fecha = new Date(ts * 1000);
  return conHora ? fecha.toLocaleString() : fecha.toLocaleDateString();
}

/**
 * Formatea un conteo de días de inactividad o devuelve el texto de respaldo.
 */
export function formatearDiasInactividad(
  dias?: number | null,
  respaldo = "—",
): string {
  if (dias == null || !Number.isFinite(dias) || dias <= 0) return respaldo;
  return `${dias} d`;
}

/**
 * Convierte una duración en segundos a una cadena legible.
 * Ejemplo: 3661 → "1h 1m 1s"
 */
export function formatearDuracion(
  totalSeconds: number | null | undefined,
): string {
  if (totalSeconds == null || totalSeconds <= 0) return "—";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (seconds > 0 || parts.length === 0) parts.push(`${seconds}s`);
  return parts.join(" ");
}

/**
 * Formatea segundos restantes a texto legible.
 * Ejemplo: 3661 → "~1h 1m"
 */
export function formatearEta(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null || totalSeconds <= 0) return "";
  if (totalSeconds < 60) return `~${Math.round(totalSeconds)}s`;
  if (totalSeconds < 3600) return `~${Math.round(totalSeconds / 60)} min`;
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.round((totalSeconds % 3600) / 60);
  if (m === 0) return `~${h}h`;
  return `~${h}h ${m}min`;
}

/**
 * Valida que un string tenga el formato de semestre esperado: 4 dígitos + A o B.
 * Ejemplo: "2025A", "2024B".
 */
export function esSemestreValido(semester: string): boolean {
  return /^\d{4}[AB]$/i.test(semester);
}

/**
 * Obtiene el semestre actual basado en la fecha actual.
 * Retorna algo como "2025A" para el primer semestre (enero-junio)
 * o "2025B" para el segundo (julio-diciembre).
 */
export function obtenerSemestreActual(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const half = month <= 6 ? "A" : "B";
  return `${year}${half}`;
}

/**
 * Formatea un semestre para presentación.
 * Ejemplo: "2025A" → "2025-A"
 */
export function formatearSemestre(semester: string): string {
  if (!esSemestreValido(semester)) return semester;
  const normalizado = semester.toUpperCase();
  return `${normalizado.slice(0, 4)}-${normalizado.slice(4)}`;
}

/**
 * Devuelve la fecha y hora actual como ISO string.
 */
export function ahoraISO(): string {
  return new Date().toISOString();
}

/**
 * Calcula el tiempo transcurrido desde una fecha ISO y lo devuelve en formato
 * legible (ej. "hace 3 horas"). Útil para mostrar cuándo se ejecutó un proceso.
 */
export function tiempoRelativo(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const date = parseISO(isoString);
    if (!isValid(date)) return "—";
    return formatDistanceToNow(date, { addSuffix: true, locale: es });
  } catch {
    return "—";
  }
}
