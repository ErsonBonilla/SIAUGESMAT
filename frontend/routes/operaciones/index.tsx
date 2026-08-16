import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaHub from "../../components/PaginaHub.tsx";
import { IconoGraficoBarras, IconoLista } from "../../utils/iconos.tsx";

export const handler = requerirAutenticacion();

export default function OperacionesHub() {
  return PaginaHub({
    title: "Operaciones",
    cards: [
      {
        icon: IconoLista,
        title: "Ejecuciones",
        description:
          "Visualiza y gestiona las ejecuciones de carga académica ETL.",
        href: "/operaciones/ejecuciones",
      },
      {
        icon: IconoGraficoBarras,
        title: "Histórico",
        description:
          "Analítica histórica de operaciones y ejecuciones por semestre.",
        href: "/operaciones/historico",
      },
    ],
  });
}
