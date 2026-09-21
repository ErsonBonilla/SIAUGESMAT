import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import CursosConsultas from "../../islands/CursosConsultas.tsx";

export const handler = requerirAutenticacion();

export default function ConsultasCursosPage() {
  return (
    <Disposicion title="Consultar cursos">
      <CursosConsultas />
    </Disposicion>
  );
}
