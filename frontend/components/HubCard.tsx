import type { ComponentChildren, JSX } from "preact";

interface HubCardProps {
  icon: (props: { class?: string }) => JSX.Element;
  title: string;
  description: string;
  href: string;
}

export default function HubCard({ icon: Icon, title, description, href }: HubCardProps) {
  return (
    <a
      href={href}
      class="group flex flex-col items-center gap-3 p-6 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] shadow-sm hover:shadow-md hover:border-[var(--accent)] transition-all duration-200 no-underline text-inherit"
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
    </a>
  );
}
