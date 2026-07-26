import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import HubCard from "../../components/HubCard.tsx";
import { SearchIcon, UploadIcon, TrashIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function UsuariosHub() {
  return (
    <Layout title="Usuarios">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <HubCard
          icon={SearchIcon}
          title="Consultar Usuarios"
          description="Consulta los usuarios existentes en Moodle por username o email."
          href="/usuarios/consultar"
        />
        <HubCard
          icon={UploadIcon}
          title="Crear Usuarios"
          description="Crea nuevos usuarios en Moodle masivamente desde un archivo CSV."
          href="/usuarios/crear"
        />
        <HubCard
          icon={TrashIcon}
          title="Eliminar Usuarios"
          description="Elimina usuarios de Moodle masivamente desde un archivo CSV."
          href="/usuarios/eliminar"
        />
      </div>
    </Layout>
  );
}
