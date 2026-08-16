// components/TarjetaReporte.tsx
import type { InfoReporte } from "../services/api.ts";
import { ETIQUETAS_REPORTES, formatearTamano } from "../utils/reportes.ts";

interface PropsTarjetaReporte {
  report: InfoReporte;
  downloading: boolean;
  disabled?: boolean;
  onClick: (report: InfoReporte) => void;
}

export default function TarjetaReporte({
  report,
  downloading,
  disabled,
  onClick,
}: PropsTarjetaReporte) {
  const label = ETIQUETAS_REPORTES[report.name] ?? report.name;
  return (
    <button
      type="button"
      onClick={() => onClick(report)}
      disabled={disabled}
      class="text-left px-4 py-3 rounded border border-[var(--border-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-50 transition-colors"
    >
      <div class="flex items-center gap-2">
        <span>📄</span>
        <span class="flex-1 text-sm font-medium text-[var(--text-primary)] truncate">
          {label}
        </span>
        {downloading
          ? (
            <span class="inline-block w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin shrink-0" />
          )
          : (
            <span class="text-xs text-[var(--text-secondary)] shrink-0">
              {formatearTamano(report.size)}
            </span>
          )}
      </div>
    </button>
  );
}
