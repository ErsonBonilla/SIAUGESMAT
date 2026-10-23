import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaAccionCsv from "../../components/PaginaAccionCsv.tsx";

export const handler = requerirAutenticacion();

export default function EliminarUsuariosPage() {
  return <PaginaAccionCsv entity="users" action="delete" />;
}
