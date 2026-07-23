// utils/theme.ts
import { signal } from "@preact/signals";

/**
 * Inicializa la señal de tema desde localStorage.
 * Se ejecuta en el ámbito del módulo, antes de que los componentes se rendericen,
 * para evitar el flash de tema al hidratar.
 * En el servidor (SSR) localStorage no está disponible, por lo que se usa `true` (oscuro).
 */
function getInitialTheme(): boolean {
  if (typeof document === "undefined") return true;
  if (typeof window !== "undefined" && (window as any).__THEME__) {
    return (window as any).__THEME__ !== "light";
  }
  return true;
}

/**
 * Señal global que controla el tema de la aplicación.
 * - `true`  → Modo oscuro (valor por defecto en SSR).
 * - `false` → Modo claro.
 */
export const darkSignal = signal(getInitialTheme());

export const DARK_THEME_VARS: Record<string, string> = {
  "--bg-primary": "#1e1e2e",
  "--bg-secondary": "#181825",
  "--bg-tertiary": "#313244",
  "--bg-skeleton": "#45475a",
  "--text-primary": "#cdd6f4",
  "--text-secondary": "#a6adc8",
  "--text-muted": "#6c7086",
  "--border-primary": "#313244",
  "--border-secondary": "#45475a",
  "--accent": "var(--brand-green)",
  "--navbar-bg": "#1e1e2e",
  "--navbar-text": "#cdd6f4",
  "--navbar-user-bg": "#313244",
  "--navbar-user-text": "#cdd6f4",
  "--accent-bg-hover": "rgba(168,168,179,0.08)",
  "--accent-rgb": "0,168,89",
  "--file-btn-bg": "rgba(0,168,89,0.12)",
  "--file-btn-text": "var(--brand-green)",
  "--file-btn-hover": "rgba(0,168,89,0.2)",
};

export const LIGHT_THEME_VARS: Record<string, string> = {
  "--bg-primary": "#FFFFFF",
  "--bg-secondary": "#F9FAFB",
  "--bg-tertiary": "#F3F4F6",
  "--bg-skeleton": "#E5E7EB",
  "--text-primary": "#111827",
  "--text-secondary": "#6B7280",
  "--text-muted": "#9CA3AF",
  "--border-primary": "#E5E7EB",
  "--border-secondary": "#D1D5DB",
  "--accent": "var(--brand-red)",
  "--navbar-bg": "#fcf1f2",
  "--navbar-text": "#821b1e",
  "--navbar-user-bg": "#fbdfe0",
  "--navbar-user-text": "#821b1e",
  "--accent-bg-hover": "rgba(237,50,55,0.06)",
  "--accent-rgb": "237,50,55",
  "--file-btn-bg": "var(--brand-red-50)",
  "--file-btn-text": "var(--brand-red)",
  "--file-btn-hover": "var(--brand-red-100)",
};

export function applyThemeVars(root: HTMLElement, vars: Record<string, string>) {
  for (const [key, value] of Object.entries(vars)) {
    root.style.setProperty(key, value);
  }
}