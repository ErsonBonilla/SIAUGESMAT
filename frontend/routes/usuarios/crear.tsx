import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import CrearUsuarios from "../../islands/CrearUsuarios.tsx";

export const handler = requerirAutenticacion();

export default function CrearUsuariosPage() {
  return (
    <Disposicion title="Crear usuarios">
      <CrearUsuarios />
    </Disposicion>
  );
}
