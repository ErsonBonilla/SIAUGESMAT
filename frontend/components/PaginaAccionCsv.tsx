import Disposicion from "./Disposicion.tsx";
import SubirCsv from "../islands/CsvUploader.tsx";
import BotonEjecucion from "./BotonEjecucion.tsx";
import { CONFIG_CSV_ENTIDADES } from "../utils/configuracion-entidad.ts";
import type { ClavePestana } from "../utils/pestanas-operaciones.ts";

interface Props {
  entity: string;
  action: "create" | "delete";
}

const EXECUTION_TAB: Record<string, ClavePestana> = {
  "courses:delete": "eliminar_cursos",
  "users:delete": "eliminar_usuarios",
  "categories:create": "crear_categorias",
  "categories:delete": "eliminar_categorias",
};

export default function PaginaAccionCsv({ entity, action }: Props) {
  const config = CONFIG_CSV_ENTIDADES[entity]?.[action];
  if (!config) return null;
  const executionTab = EXECUTION_TAB[`${entity}:${action}`];
  return (
    <Disposicion title={config.title}>
      <SubirCsv
        description={config.description}
        uploadEndpoint={config.endpoint}
        etiquetaSingular={config.singular}
        etiquetaPlural={config.plural}
        action={action}
        help={config.help}
      />
      {executionTab && <BotonEjecucion tab={executionTab} />}
    </Disposicion>
  );
}
