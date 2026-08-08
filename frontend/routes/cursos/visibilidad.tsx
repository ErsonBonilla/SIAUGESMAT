import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import VisibilidadMasivaIsland from "../../islands/VisibilidadMasivaIsland.tsx";

export const handler = requireAuth();

export default function BulkVisibilityPage() {
  return (
    <Layout title="Visibilidad de cursos">
      <VisibilidadMasivaIsland />
    </Layout>
  );
}
