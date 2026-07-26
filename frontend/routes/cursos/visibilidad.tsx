import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import BulkVisibilityIsland from "../../islands/BulkVisibilityIsland.tsx";

export const handler = requireAuth();

export default function BulkVisibilityPage() {
  return (
    <Layout title="Visibilidad de cursos">
      <BulkVisibilityIsland />
    </Layout>
  );
}
