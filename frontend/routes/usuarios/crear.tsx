import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CrearUsuarios from "../../islands/CrearUsuarios.tsx";

export const handler = requireAuth();

export default function CrearUsuariosPage() {
  return (
    <Layout title="Crear usuarios">
      <CrearUsuarios />
    </Layout>
  );
}
