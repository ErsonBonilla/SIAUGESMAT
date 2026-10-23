import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import VisibilidadMasivaIsland from "../../islands/VisibilidadMasivaIsland.tsx";

export const handler = requerirAutenticacion();

export default function PaginaVisibilidadMasiva() {
  return (
    <Disposicion title="Visibilidad de cursos">
      <VisibilidadMasivaIsland />
    </Disposicion>
  );
}
