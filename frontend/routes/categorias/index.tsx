import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import HubCard from "../../components/HubCard.tsx";
import { SearchIcon, UploadIcon, TrashIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function CategoriasHub() {
  return (
    <Layout title="Categorías">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <HubCard
          icon={SearchIcon}
          title="Consultar Categorías"
          description="Consulta las categorías existentes en Moodle por idnumber."
          href="/categorias/consultar"
        />
        <HubCard
          icon={UploadIcon}
          title="Crear Categorías"
          description="Crea nuevas categorías en Moodle masivamente desde un archivo CSV."
          href="/categorias/crear"
        />
        <HubCard
          icon={TrashIcon}
          title="Eliminar Categorías"
          description="Elimina categorías de Moodle masivamente desde un archivo CSV."
          href="/categorias/eliminar"
        />
      </div>
    </Layout>
  );
}
