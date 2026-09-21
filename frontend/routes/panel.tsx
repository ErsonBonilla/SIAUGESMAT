// routes/panel.tsx
import { requerirAutenticacion } from "../utils/guarda-autenticacion.ts";
import PanelIsland from "../islands/PanelIsland.tsx";

export const handler = requerirAutenticacion();

export default function PaginaPanel() {
  return <PanelIsland />;
}
