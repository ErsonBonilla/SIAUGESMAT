import { useSignal } from "@preact/signals";
import type { JSX } from "preact";
import Layout from "./Layout.tsx";

interface TabDef {
  key: string;
  label: string;
}

interface Props {
  title: string;
  description: string;
  tabs: readonly TabDef[];
  renderTab: (key: string) => JSX.Element;
}

export default function TabbedPage(
  { title, description, tabs, renderTab }: Props,
) {
  const tab = useSignal(tabs[0].key);
  const active = "bg-[var(--accent)] text-white";
  const inactive =
    "border bg-[var(--bg-primary)] border-[var(--border-secondary)] text-[var(--text-secondary)]";

  return (
    <Layout title={title}>
      <p
        class="text-sm text-[var(--text-secondary)] mt-1"
        style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}
      >
        {description}
      </p>
      <div class="flex flex-wrap gap-2 mb-6">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => tab.value = t.key}
            class={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
              tab.value === t.key ? active : inactive
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
        {renderTab(tab.value)}
      </div>
    </Layout>
  );
}
