import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaAccionCsv from "../../components/PaginaAccionCsv.tsx";

export const handler = requerirAutenticacion();

export default function CrearCategoriasPage() {
  return <PaginaAccionCsv entity="categories" action="create" />;
}
