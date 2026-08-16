import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaAccionCsv from "../../components/PaginaAccionCsv.tsx";

export const handler = requerirAutenticacion();

export default function EliminarCategoriasPage() {
  return <PaginaAccionCsv entity="categories" action="delete" />;
}
