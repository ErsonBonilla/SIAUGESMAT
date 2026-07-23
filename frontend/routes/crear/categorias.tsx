import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import CsvUploader from "../../islands/CsvUploader.tsx";

export const handler = requireAuth();

export default function CrearCategoriasPage() {
  return (
    <Layout title="Crear categorías">
      <CsvUploader
        title="Crear categorías"
        description="Subí un archivo CSV con la columna 'name' (obligatoria) y opcionalmente 'idnumber', 'parent', 'description' y 'visible'. Las categorías se crean en árbol bajo 'IDEAD' (idnumber: DISTANCIA)."
        uploadEndpoint="categories/create-csv"
        labelSingular="categoría"
        labelPlural="categorías"
        action="create"
      />
    </Layout>
  );
}
