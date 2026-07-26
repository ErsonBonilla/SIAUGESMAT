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
          {
            key: "pattern",
            label: "Formato de código",
            type: "select",
            options: [
              { value: "all", label: "Todos los códigos" },
              { value: "6segments", label: "6 segmentos (CAL_0852_sIV_5031216_G-1_29114506)" },
              { value: "5segments", label: "5 segmentos (CHA_0845_sVI_102131_G-1)" },
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
