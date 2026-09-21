import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaHub from "../../components/PaginaHub.tsx";
import {
  IconoAlternar,
  IconoBuscar,
  IconoOjo,
  IconoPapelera,
  IconoSubir,
} from "../../utils/iconos.tsx";

export const handler = requerirAutenticacion();

export default function CursosHub() {
  return PaginaHub({
    title: "Cursos",
    cards: [
      {
        icon: IconoBuscar,
        title: "Consultar Cursos",
        description: "Consulta los cursos existentes en Moodle por shortname.",
        href: "/cursos/consultar",
      },
      {
        icon: IconoSubir,
        title: "Crear Cursos",
        description:
          "Crea cursos en Moodle desde el archivo de carga académica (Excel).",
        href: "/cursos/crear",
      },
      {
        icon: IconoPapelera,
        title: "Eliminar Cursos",
        description:
          "Elimina cursos de Moodle masivamente desde un archivo CSV.",
        href: "/cursos/eliminar",
      },
      {
        icon: IconoOjo,
        title: "Visibilidad Cursos",
        description:
          "Muestra u oculta cursos existentes en Moodle masivamente.",
        href: "/cursos/visibilidad",
      },
      {
        icon: IconoAlternar,
        title: "Gestionar Novedades",
        description:
          "Compara dos cargas académicas del mismo semestre y gestiona cambios de asignación docente.",
        href: "/cursos/novedades",
      },
    ],
  });
}
