import { requireAuth } from "../../utils/auth-guard.ts";
import TabbedPage from "../../components/TabbedPage.tsx";
import ExecutionList from "../../islands/ExecutionList.tsx";
import OperationList from "../../islands/OperationList.tsx";
import { OPERATIONS_TABS } from "../../utils/operations-tabs.ts";

export const handler = requireAuth();

export default function OperacionesPage() {
  return (
    <TabbedPage
      title="Ejecuciones"
      description="Historial de todas las ejecuciones del sistema."
      tabs={OPERATIONS_TABS}
      renderTab={(key) => {
        const tab = OPERATIONS_TABS.find((t) => t.key === key)!;
        return tab.component === "etl" ? <ExecutionList /> : (
          <OperationList
            defaultEntity={tab.entity!}
            defaultAction={tab.action!}
          />
        );
      }}
    />
  );
}
