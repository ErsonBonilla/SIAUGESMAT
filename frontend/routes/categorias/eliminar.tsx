import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CsvUploader from "../../islands/CsvUploader.tsx";

export const handler = requireAuth();

export default function EliminarCategoriasPage() {
  return (
    <Layout title="Eliminar categorías">
      <CsvUploader
        title="Eliminar categorías"
        description="Subí un archivo CSV con la columna 'idnumber' que contenga los identificadores de las categorías a eliminar."
        uploadEndpoint="categories/upload-csv"
        labelSingular="categoría"
        labelPlural="categorías"
        action="delete"
      />
    </Layout>
  );
}
