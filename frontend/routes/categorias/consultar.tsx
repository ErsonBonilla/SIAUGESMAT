import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import PaginaConsulta from "../../components/PaginaConsulta.tsx";

export const handler = requerirAutenticacion();

export default function ConsultasCategoriasPage() {
  return <PaginaConsulta entity="categories" />;
}
