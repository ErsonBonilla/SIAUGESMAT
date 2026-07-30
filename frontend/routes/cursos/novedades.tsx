import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import NovedadesIsland from "../../islands/NovedadesIsland.tsx";

export const handler = requireAuth();

export default function NovedadesPage() {
  return (
    <Layout title="Gestionar novedades">
      <NovedadesIsland />
    </Layout>
  );
}
