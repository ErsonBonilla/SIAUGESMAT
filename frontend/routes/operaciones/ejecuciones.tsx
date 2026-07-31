import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import EjecucionesTabs from "../../islands/EjecucionesTabs.tsx";

export const handler = requireAuth();

export default function OperacionesPage() {
  return (
    <Layout title="Ejecuciones">
      <p
        class="text-sm text-[var(--text-secondary)] mt-1"
        style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}
      >
        Historial de todas las ejecuciones del sistema.
      </p>
      <EjecucionesTabs />
    </Layout>
  );
}
