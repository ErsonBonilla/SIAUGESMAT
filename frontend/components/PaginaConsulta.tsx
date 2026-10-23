import Disposicion from "./Disposicion.tsx";
import TablaConsultaIsland from "../islands/TablaConsultaIsland.tsx";
import { CONFIG_CONSULTA_ENTIDADES } from "../utils/configuracion-entidad.ts";

interface Props {
  entity: string;
}

export default function PaginaConsulta({ entity }: Props) {
  const config = CONFIG_CONSULTA_ENTIDADES[entity];
  if (!config) return null;
  return (
    <Disposicion title={config.title}>
      <TablaConsultaIsland entity={entity} {...config} />
    </Disposicion>
  );
}
