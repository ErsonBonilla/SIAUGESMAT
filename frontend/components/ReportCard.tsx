// components/ReportCard.tsx
import type { ReportInfo } from "../services/api.ts";
import { formatSize, REPORT_LABELS } from "../utils/reports.ts";

interface ReportCardProps {
  report: ReportInfo;
  downloading: boolean;
  disabled?: boolean;
  onClick: (report: ReportInfo) => void;
}

export default function ReportCard({
  report,
  downloading,
  disabled,
  onClick,
}: ReportCardProps) {
  const label = REPORT_LABELS[report.name] ?? report.name;
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
              {formatSize(report.size)}
            </span>
          )}
      </div>
    </button>
  );
}
