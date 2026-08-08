import { requireAuth } from "../../utils/auth-guard.ts";
import HubPage from "../../components/HubPage.tsx";
import { SearchIcon, TrashIcon, UploadIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function UsuariosHub() {
  return HubPage({
    title: "Usuarios",
    cards: [
      {
        icon: SearchIcon,
        title: "Consultar Usuarios",
        description:
          "Consulta los usuarios existentes en Moodle por username o email.",
        href: "/usuarios/consultar",
      },
      {
        icon: UploadIcon,
        title: "Crear Usuarios",
        description:
          "Crea nuevos usuarios en Moodle masivamente desde un archivo CSV.",
        href: "/usuarios/crear",
      },
      {
        icon: TrashIcon,
        title: "Eliminar Usuarios",
        description:
          "Elimina usuarios de Moodle masivamente desde un archivo CSV.",
        href: "/usuarios/eliminar",
      },
    ],
  });
}
