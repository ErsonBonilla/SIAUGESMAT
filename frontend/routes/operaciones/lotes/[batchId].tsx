// routes/operaciones/lotes/[batchId].tsx
import type { PageProps } from "@fresh/core";
import { requireAuth } from "../../../utils/auth-guard.ts";
import Layout from "../../../components/Layout.tsx";
import BatchDetailIsland from "../../../islands/BatchDetailIsland.tsx";

export const handler = requireAuth();

export default function BatchDetailPage({ params }: PageProps) {
  const batchId = decodeURIComponent(params.batchId);

  return (
    <Layout title={`Lote ${batchId.slice(0, 8)}...`}>
      <BatchDetailIsland batchId={batchId} />
    </Layout>
  );
}
