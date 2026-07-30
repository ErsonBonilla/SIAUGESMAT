import { requireAuth } from "../../utils/auth-guard.ts";
import TabbedPage from "../../components/TabbedPage.tsx";
import HistoricoIsland from "../../islands/Historico.tsx";
import OperationHistorico from "../../islands/HistoricoOperaciones.tsx";
import { OPERATIONS_TABS } from "../../utils/operations-tabs.ts";

export const handler = requireAuth();

export default function HistoricoPage() {
  return (
    <TabbedPage
      title="Histórico de operaciones"
      description="Métricas históricas de todas las operaciones del sistema."
      tabs={OPERATIONS_TABS}
      renderTab={(key) => {
        const tab = OPERATIONS_TABS.find((t) => t.key === key)!;
        return tab.component === "etl"
          ? <HistoricoIsland />
          : (
            <OperationHistorico
              entityType={tab.entity!}
              action={tab.action!}
            />
          );
      }}
    />
  );
}
