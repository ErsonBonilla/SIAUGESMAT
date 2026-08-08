// routes/cursos/crear.tsx
import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CargaIsland from "../../islands/CargaIsland.tsx";

export const handler = requireAuth();

export default function UploadPage() {
  return (
    <Layout title="Crear cursos">
      <CargaIsland />
    </Layout>
  );
}
