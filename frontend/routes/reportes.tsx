// routes/reportes.tsx
import type { PageProps } from "@fresh/core";
import { requireAuth } from "../utils/auth-guard.ts";
import Layout from "../components/Layout.tsx";
import ReportesIsland from "../islands/Reportes.tsx";

export const handler = requireAuth();

export default function ReportesPage({ url }: PageProps) {
  const executionId = parseInt(url.searchParams.get("execution_id") || "0");

  if (!executionId) {
    return (
      <Layout title="Reportes">
        <p class="text-[var(--text-secondary)] text-sm">
          Seleccione una ejecución desde{" "}
          <a
            href="/operaciones/ejecuciones"
            class="text-[var(--accent)] hover:underline"
          >
            el listado de ejecuciones
          </a>{" "}
          para ver sus gráficos y descargar reportes.
        </p>
      </Layout>
    );
  }

  return (
    <Layout title={`Reportes - Ejecución #${executionId}`}>
      <ReportesIsland executionId={executionId} />
    </Layout>
  );
}
