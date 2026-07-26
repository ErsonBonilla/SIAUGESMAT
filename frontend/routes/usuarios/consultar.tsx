import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import QueryTable from "../../islands/QueryTable.tsx";

export const handler = requireAuth();

export default function ConsultasUsuariosPage() {
  return (
    <Layout title="Consultar usuarios">
      <QueryTable
        entity="users"
        title="Usuarios"
        searchPlaceholder="Buscar por username o email..."
        searchKey="search"
        filters={[
          {
            key: "role",
            label: "Rol",
            type: "select",
            options: [
              { value: "all", label: "Todos los usuarios" },
              { value: "professor", label: "Profesores (editingteacher)" },
            ],
          },
          {
            key: "status",
            label: "Filtro adicional",
            type: "select",
            options: [
              { value: "", label: "Sin filtro adicional" },
              { value: "never_logged_in", label: "Nunca ingresaron" },
            ],
          },
        ]}
        columns={[
          { key: "username", label: "Username" },
          { key: "email", label: "Email" },
          { key: "firstname", label: "Nombres" },
          { key: "lastname", label: "Apellidos" },
          {
            key: "lastlogin",
            label: "Último login",
            render: (v) => typeof v === "number" && v > 0
              ? new Date(v * 1000).toLocaleString()
              : "Nunca",
          },
        ]}
      />
    </Layout>
  );
}
