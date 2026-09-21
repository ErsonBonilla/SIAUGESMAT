import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaHub from "../../components/PaginaHub.tsx";
import { IconoBuscar, IconoPapelera, IconoSubir } from "../../utils/iconos.tsx";

export const handler = requerirAutenticacion();

export default function UsuariosHub() {
  return PaginaHub({
    title: "Usuarios",
    cards: [
      {
        icon: IconoBuscar,
        title: "Consultar Usuarios",
        description:
          "Consulta los usuarios existentes en Moodle por username o email.",
        href: "/usuarios/consultar",
      },
      {
        icon: IconoSubir,
        title: "Crear Usuarios",
        description:
          "Crea nuevos usuarios en Moodle masivamente desde un archivo CSV.",
        href: "/usuarios/crear",
      },
      {
        icon: IconoPapelera,
        title: "Eliminar Usuarios",
        description:
          "Elimina usuarios de Moodle masivamente desde un archivo CSV.",
        href: "/usuarios/eliminar",
      },
    ],
  });
}
