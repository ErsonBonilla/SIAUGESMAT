// routes/jobs/[id].tsx
import type { PageProps } from "@fresh/core";
import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import JobDetailIsland from "../../islands/JobDetailIsland.tsx";

export const handler = requireAuth();

export default function JobDetailPage({ params }: PageProps) {
  const executionId = parseInt(params.id);

  return (
    <Layout title={`Ejecución #${executionId}`}>
      <JobDetailIsland executionId={executionId} />
    </Layout>
  );
}
