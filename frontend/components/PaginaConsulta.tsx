import Disposicion from "./Disposicion.tsx";
import TablaConsultaIsland from "../islands/TablaConsultaIsland.tsx";
import { ENTITY_CONSULT_CONFIGS } from "../utils/configuracion-entidad.ts";

interface Props {
  entity: string;
}

export default function PaginaConsulta({ entity }: Props) {
  const config = ENTITY_CONSULT_CONFIGS[entity];
  if (!config) return null;
  return (
    <Disposicion title={config.title}>
      <TablaConsultaIsland entity={entity} {...config} />
    </Disposicion>
  );
}
