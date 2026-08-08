import type { JSX } from "preact";

interface HubCardProps {
  icon: (props: { class?: string }) => JSX.Element;
  title: string;
  description: string;
  href: string;
  /** Si existe, muestra un botón en la esquina inferior derecha que abre
   *  /operaciones/ejecuciones con esa pestaña de procedimiento precargada. */
  executionTab?: string | null;
}

export default function HubCard(
  { icon: Icon, title, description, href, executionTab }: HubCardProps,
) {
  const goToExecution = (e: Event) => {
    e.preventDefault();
    e.stopPropagation();
    window.location.href = `/operaciones/ejecuciones?tab=${executionTab}`;
  };

  return (
    <a
      href={href}
      class="group relative flex flex-col items-center gap-3 p-6 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] shadow-sm hover:shadow-md hover:border-[var(--accent)] transition-all duration-200 no-underline text-inherit"
    >
      <div class="w-14 h-14 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center group-hover:scale-110 transition-transform duration-200">
        <Icon class="w-7 h-7 text-[var(--accent)]" />
      </div>
      <h3 class="text-base font-semibold text-[var(--text-primary)] text-center">
        {title}
      </h3>
      <p class="text-xs text-[var(--text-secondary)] text-center leading-relaxed">
        {description}
      </p>
      {executionTab && (
        <button
          type="button"
          onClick={goToExecution}
          class="absolute bottom-3 right-3 inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border border-[var(--border-secondary)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent)] transition-colors cursor-pointer"
          title={`Ver ejecuciones de ${title}`}
        >
          Ejecución
          <svg
            class="w-3.5 h-3.5"
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
      )}
    </a>
  );
}
