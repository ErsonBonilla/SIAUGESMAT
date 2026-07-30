import { requireAuth } from "../../utils/auth-guard.ts";
import HubPage from "../../components/HubPage.tsx";
import { ChartBarIcon, ListIcon } from "../../utils/icons.tsx";

export const handler = requireAuth();

export default function OperacionesHub() {
  return HubPage({
    title: "Operaciones",
    cards: [
      {
        icon: ListIcon,
        title: "Ejecuciones",
        description:
          "Visualiza y gestiona las ejecuciones de carga académica ETL.",
        href: "/operaciones/ejecuciones",
      },
      {
        icon: ChartBarIcon,
        title: "Histórico",
        description:
          "Analítica histórica de operaciones y ejecuciones por semestre.",
        href: "/operaciones/historico",
      },
    ],
  });
}
