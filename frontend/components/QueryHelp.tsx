// components/QueryHelp.tsx
import { useSignal } from "@preact/signals";

export interface QueryHelpSection {
  title: string;
  body: string | string[];
}

interface QueryHelpProps {
  sections: QueryHelpSection[];
}

export default function QueryHelp({ sections }: QueryHelpProps) {
  const open = useSignal(false);

  return (
    <div class="mb-6 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)]">
      <button
        type="button"
        onClick={() => (open.value = !open.value)}
        class="w-full flex items-center justify-between gap-2 px-4 py-3 text-left cursor-pointer bg-transparent border-none"
      >
        <span class="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <span aria-hidden>❓</span>
          Cómo usar esta consulta
        </span>
        <span
          class="text-sm text-[var(--text-muted)] transition-transform duration-300"
          style={{ transform: open.value ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          ▼
        </span>
      </button>

      {open.value && (
        <div class="px-4 pb-4 space-y-4 animate-scaleIn">
          {sections.map((section) => (
            <div key={section.title}>
              <p class="text-xs font-semibold text-[var(--text-secondary)] mb-1.5 uppercase tracking-wide">
                {section.title}
              </p>
              {Array.isArray(section.body)
                ? (
                  <ul class="list-disc list-inside text-sm text-[var(--text-primary)] space-y-1">
                    {section.body.map((item, idx) => <li key={idx}>{item}</li>)}
                  </ul>
                )
                : (
                  <p class="text-sm text-[var(--text-primary)]">
                    {section.body}
                  </p>
                )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
