import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import UsuariosConsultas from "../../islands/UsuariosConsultas.tsx";

export const handler = requireAuth();

export default function ConsultasUsuariosPage() {
  return (
    <Layout title="Consultar usuarios">
      <UsuariosConsultas />
    </Layout>
  );
}
