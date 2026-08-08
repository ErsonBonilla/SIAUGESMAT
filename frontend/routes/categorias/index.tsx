import { requireAuth } from "../../utils/auth-guard.ts";
import HubPage from "../../components/HubPage.tsx";
import { SearchIcon, TrashIcon, UploadIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function CategoriasHub() {
  return HubPage({
    title: "Categorías",
    cards: [
      {
        icon: SearchIcon,
        title: "Consultar Categorías",
        description:
          "Consulta las categorías existentes en Moodle por idnumber.",
        href: "/categorias/consultar",
      },
      {
        icon: UploadIcon,
        title: "Crear Categorías",
        description:
          "Crea nuevas categorías en Moodle masivamente desde un archivo CSV.",
        href: "/categorias/crear",
      },
      {
        icon: TrashIcon,
        title: "Eliminar Categorías",
        description:
          "Elimina categorías de Moodle masivamente desde un archivo CSV.",
        href: "/categorias/eliminar",
      },
    ],
  });
}
