import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaHub from "../../components/PaginaHub.tsx";
import { IconoBuscar, IconoPapelera, IconoSubir } from "../../utils/iconos.tsx";

export const handler = requerirAutenticacion();

export default function CategoriasHub() {
  return PaginaHub({
    title: "Categorías",
    cards: [
      {
        icon: IconoBuscar,
        title: "Consultar Categorías",
        description:
          "Consulta las categorías existentes en Moodle por idnumber.",
        href: "/categorias/consultar",
      },
      {
        icon: IconoSubir,
        title: "Crear Categorías",
        description:
          "Crea nuevas categorías en Moodle masivamente desde un archivo CSV.",
        href: "/categorias/crear",
      },
      {
        icon: IconoPapelera,
        title: "Eliminar Categorías",
        description:
          "Elimina categorías de Moodle masivamente desde un archivo CSV.",
        href: "/categorias/eliminar",
      },
    ],
  });
}
