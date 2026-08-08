// routes/ejecuciones/[id].tsx
import type { PageProps } from "@fresh/core";
import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import DetalleEjecucionIsland from "../../islands/DetalleEjecucionIsland.tsx";

export const handler = requireAuth();

export default function JobDetailPage({ params }: PageProps) {
  const executionId = parseInt(params.id);

  return (
    <Layout title={`Ejecución #${executionId}`}>
      <DetalleEjecucionIsland executionId={executionId} />
    </Layout>
  );
}
