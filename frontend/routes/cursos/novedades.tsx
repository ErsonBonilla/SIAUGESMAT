import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import NovedadesIsland from "../../islands/NovedadesIsland.tsx";

export const handler = requerirAutenticacion();

export default function NovedadesPage() {
  return (
    <Disposicion title="Gestionar novedades">
      <NovedadesIsland />
    </Disposicion>
  );
}
