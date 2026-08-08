import { requireAuth } from "../../utils/auth-guard.ts";
import HubPage from "../../components/HubPage.tsx";
import {
  EyeIcon,
  SearchIcon,
  SwitchIcon,
  TrashIcon,
  UploadIcon,
} from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function CursosHub() {
  return HubPage({
    title: "Cursos",
    cards: [
      {
        icon: SearchIcon,
        title: "Consultar Cursos",
        description: "Consulta los cursos existentes en Moodle por shortname.",
        href: "/cursos/consultar",
      },
      {
        icon: UploadIcon,
        title: "Crear Cursos",
        description:
          "Crea cursos en Moodle desde el archivo de carga académica (Excel).",
        href: "/cursos/crear",
        executionTab: "crear_cursos",
      },
      {
        icon: TrashIcon,
        title: "Eliminar Cursos",
        description:
          "Elimina cursos de Moodle masivamente desde un archivo CSV.",
        href: "/cursos/eliminar",
        executionTab: "eliminar_cursos",
      },
      {
        icon: EyeIcon,
        title: "Visibilidad Cursos",
        description:
          "Muestra u oculta cursos existentes en Moodle masivamente.",
        href: "/cursos/visibilidad",
        executionTab: "visibilidad_cursos",
      },
      {
        icon: SwitchIcon,
        title: "Gestionar Novedades",
        description:
          "Compara dos cargas académicas del mismo semestre y gestiona cambios de asignación docente.",
        href: "/cursos/novedades",
      },
    ],
  });
}
