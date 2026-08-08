// components/ExecutionButton.tsx
import type { TabKey } from "../utils/operations-tabs.ts";

interface ExecutionButtonProps {
  tab: TabKey;
  label?: string;
}

export default function ExecutionButton(
  { tab, label = "Ejecución" }: ExecutionButtonProps,
) {
  const goToExecution = () => {
    window.location.href = `/operaciones/ejecuciones?tab=${tab}`;
  };

  return (
    <div class="flex justify-end mt-6">
      <button
        type="button"
        onClick={goToExecution}
        class="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-medium border border-[var(--border-secondary)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent)] transition-colors cursor-pointer"
        title="Ver ejecuciones de este procedimiento"
      >
        {label}
        <svg
          class="w-4 h-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 5l7 7-7 7"
          />
        </svg>
      </button>
    </div>
  );
}
