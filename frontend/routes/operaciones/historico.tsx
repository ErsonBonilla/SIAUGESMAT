// routes/operaciones/historico.tsx
import { useSignal } from "@preact/signals";
import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import HistoricoIsland from "../../islands/HistoricoIsland.tsx";
import OperationHistorico from "../../islands/OperationHistorico.tsx";
import { OPERATIONS_TABS, type TabKey } from "../../utils/operations-tabs.ts";

export const handler = requireAuth();

export default function HistoricoPage() {
  const tab = useSignal<TabKey>("crear_cursos");

  const active = "bg-[var(--accent)] text-white";
  const inactive = "border bg-[var(--bg-primary)] border-[var(--border-secondary)] text-[var(--text-secondary)]";

  const current = OPERATIONS_TABS.find((t) => t.key === tab.value)!;

  return (
    <Layout title="Histórico de operaciones">
      <p class="text-sm text-[var(--text-secondary)] mt-1" style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}>
        Métricas históricas de todas las operaciones del sistema.
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
          ? <HistoricoIsland />
          : <OperationHistorico entityType={current.entity!} action={current.action!} />}
      </div>
    </Layout>
  );
}
