import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import HubCard from "../../components/HubCard.tsx";
import { ListIcon, ChartBarIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function OperacionesHub() {
  return (
    <Layout title="Operaciones">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <HubCard
          icon={ListIcon}
          title="Ejecuciones"
          description="Visualiza y gestiona las ejecuciones de carga académica ETL."
          href="/operaciones/ejecuciones"
        />
        <HubCard
          icon={ChartBarIcon}
          title="Histórico"
          description="Analítica histórica de operaciones y ejecuciones por semestre."
          href="/operaciones/historico"
        />
      </div>
    </Layout>
  );
}
