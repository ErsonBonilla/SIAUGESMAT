import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import HistoricoTabs from "../../islands/HistoricoTabs.tsx";

export const handler = requireAuth();

export default function HistoricoPage() {
  return (
    <Layout title="Histórico de operaciones">
      <p
        class="text-sm text-[var(--text-secondary)] mt-1"
        style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}
      >
        Métricas históricas de todas las operaciones del sistema.
      </p>
      <HistoricoTabs />
    </Layout>
  );
}
