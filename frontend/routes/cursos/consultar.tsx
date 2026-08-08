import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CursosConsultas from "../../islands/CursosConsultas.tsx";

export const handler = requireAuth();

export default function ConsultasCursosPage() {
  return (
    <Layout title="Consultar cursos">
      <CursosConsultas />
    </Layout>
  );
}
