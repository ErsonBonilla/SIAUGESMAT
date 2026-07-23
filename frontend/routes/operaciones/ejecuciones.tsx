// routes/operaciones/ejecuciones.tsx
import { useSignal } from "@preact/signals";
import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import ExecutionList from "../../islands/ExecutionList.tsx";
import OperationList from "../../islands/OperationList.tsx";
import { OPERATIONS_TABS, type TabKey } from "../../utils/operations-tabs.ts";

export const handler = requireAuth();

export default function OperacionesPage() {
  const tab = useSignal<TabKey>("crear_cursos");

  const active = "bg-[var(--accent)] text-white";
  const inactive = "border bg-[var(--bg-primary)] border-[var(--border-secondary)] text-[var(--text-secondary)]";

  const current = OPERATIONS_TABS.find((t) => t.key === tab.value)!;

  return (
    <Layout title="Ejecuciones">
      <p class="text-sm text-[var(--text-secondary)] mt-1" style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}>
        Historial de todas las ejecuciones del sistema.
      </p>

      <div class="flex flex-wrap gap-2 mb-6">
        {OPERATIONS_TABS.map((t) => (
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
        {current.component === "etl"
          ? <ExecutionList />
          : <OperationList defaultEntity={current.entity!} defaultAction={current.action!} />}
      </div>
    </Layout>
  );
}
