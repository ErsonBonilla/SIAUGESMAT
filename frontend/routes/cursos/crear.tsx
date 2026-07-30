// routes/cursos/crear.tsx
import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import UploadIsland from "../../islands/UploadIsland.tsx";

export const handler = requireAuth();

export default function UploadPage() {
  return (
    <Layout title="Crear cursos">
      <UploadIsland />
    </Layout>
  );
}
