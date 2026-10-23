// routes/operaciones/lotes/[batchId].tsx
import type { PageProps } from "@fresh/core";
import { requerirAutenticacion } from "../../../utils/guarda-autenticacion.ts";
import Disposicion from "../../../components/Disposicion.tsx";
import DetalleLoteIsland from "../../../islands/DetalleLoteIsland.tsx";

export const handler = requerirAutenticacion();

export default function PaginaDetalleLote({ params }: PageProps) {
  const batchId = decodeURIComponent(params.batchId);

  return (
    <Disposicion title={`Lote ${batchId.slice(0, 8)}...`}>
      <DetalleLoteIsland batchId={batchId} />
    </Disposicion>
  );
}
