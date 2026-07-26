import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CsvUploader from "../../islands/CsvUploader.tsx";

export const handler = requireAuth();

export default function EliminarUsuariosPage() {
  return (
    <Layout title="Eliminar usuarios">
      <CsvUploader
        title="Eliminar usuarios"
        description="Subí un archivo CSV con la columna 'username' que contenga los nombres de usuario a eliminar."
        uploadEndpoint="users/upload-csv"
        labelSingular="usuario"
        labelPlural="usuarios"
        action="delete"
      />
    </Layout>
  );
}
