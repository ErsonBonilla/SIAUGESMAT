// routes/cursos/crear.tsx
import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import CargaIsland from "../../islands/CargaIsland.tsx";

export const handler = requerirAutenticacion();

export default function PaginaSubida() {
  return (
    <Disposicion title="Crear cursos">
      <CargaIsland />
    </Disposicion>
  );
}
