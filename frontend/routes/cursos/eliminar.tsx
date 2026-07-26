import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CsvUploader from "../../islands/CsvUploader.tsx";

export const handler = requireAuth();

export default function EliminarCursosPage() {
  return (
    <Layout title="Eliminar cursos">
      <CsvUploader
        title="Eliminar cursos"
        description="Subí un archivo CSV con la columna 'shortname' que contenga los nombres cortos de los cursos a eliminar."
        uploadEndpoint="courses/upload-csv"
        labelSingular="curso"
        labelPlural="cursos"
        action="delete"
      />
    </Layout>
  );
}
