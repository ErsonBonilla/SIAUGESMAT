// routes/ingreso.tsx
import { redirigirSiAutenticado } from "../utils/guarda-autenticacion.ts";
import PaginaLoginIsland from "../islands/PaginaLoginIsland.tsx";

export const handler = redirigirSiAutenticado();

export default function PaginaIngreso() {
  return <PaginaLoginIsland />;
}
