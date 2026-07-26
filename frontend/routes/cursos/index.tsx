import { requireAuth } from "../../utils/auth-guard.ts";
import Layout from "../../components/Layout.tsx";
import HubCard from "../../components/HubCard.tsx";
import { SearchIcon, UploadIcon, TrashIcon, EyeIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function CursosHub() {
  return (
    <Layout title="Cursos">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <HubCard
          icon={SearchIcon}
          title="Consultar Cursos"
          description="Consulta los cursos existentes en Moodle por shortname."
          href="/cursos/consultar"
        />
        <HubCard
          icon={UploadIcon}
          title="Crear Cursos"
          description="Crea cursos en Moodle desde el archivo de carga académica (Excel)."
          href="/cursos/crear"
        />
        <HubCard
          icon={TrashIcon}
          title="Eliminar Cursos"
          description="Elimina cursos de Moodle masivamente desde un archivo CSV."
          href="/cursos/eliminar"
        />
        <HubCard
          icon={EyeIcon}
          title="Visibilidad Cursos"
          description="Muestra u oculta cursos existentes en Moodle masivamente."
          href="/cursos/visibilidad"
        />
      </div>
    </Layout>
  );
}
