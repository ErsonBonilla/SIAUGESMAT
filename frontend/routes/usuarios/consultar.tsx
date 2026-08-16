import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import UsuariosConsultas from "../../islands/UsuariosConsultas.tsx";

export const handler = requerirAutenticacion();

export default function ConsultasUsuariosPage() {
  return (
    <Disposicion title="Consultar usuarios">
      <UsuariosConsultas />
    </Disposicion>
  );
}
