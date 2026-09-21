// routes/ejecuciones/[id].tsx
import type { PageProps } from "@fresh/core";
import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import DetalleEjecucionIsland from "../../islands/DetalleEjecucionIsland.tsx";

export const handler = requerirAutenticacion();

export default function PaginaDetalleEjecucion({ params }: PageProps) {
  const executionId = parseInt(params.id);

  return (
    <Disposicion title={`Ejecución #${executionId}`}>
      <DetalleEjecucionIsland executionId={executionId} />
    </Disposicion>
  );
}
