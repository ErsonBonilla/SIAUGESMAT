import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import QueryTable from "../../islands/QueryTable.tsx";

export const handler = requireAuth();

export default function ConsultasCursosPage() {
  return (
    <Layout title="Consultar cursos">
      <QueryTable
        entity="courses"
        title="Cursos"
        searchPlaceholder="Buscar por shortname..."
        searchKey="search"
        filters={[
          {
            key: "status",
            label: "Estado",
            type: "select",
            options: [
              { value: "all", label: "Todos los cursos" },
              { value: "unused_6months", label: "Sin uso (> 6 meses)" },
            ],
          },
        ]}
        columns={[
          { key: "id", label: "ID" },
          { key: "shortname", label: "Shortname" },
          { key: "fullname", label: "Nombre completo" },
          { key: "categoryname", label: "Categoría" },
          {
            key: "visible",
            label: "Visible",
            render: (v) => v == 1 ? "Sí" : "No",
          },
        ]}
      />
    </Layout>
  );
}
