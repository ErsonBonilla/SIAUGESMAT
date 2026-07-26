import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import QueryTable from "../../islands/QueryTable.tsx";

export const handler = requireAuth();

export default function ConsultasCategoriasPage() {
  return (
    <Layout title="Consultar categorías">
      <QueryTable
        entity="categories"
        title="Categorías"
        searchPlaceholder="Buscar por idnumber..."
        searchKey="search"
        columns={[
          { key: "id", label: "ID" },
          { key: "idnumber", label: "ID Number" },
          { key: "name", label: "Nombre" },
          { key: "parent", label: "Padre" },
          { key: "coursecount", label: "Cursos" },
        ]}
      />
    </Layout>
  );
}
