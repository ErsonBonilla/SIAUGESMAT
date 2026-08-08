import Layout from "./Layout.tsx";
import CsvUploader from "../islands/CsvUploader.tsx";
import ExecutionButton from "./ExecutionButton.tsx";
import { ENTITY_CSV_CONFIGS } from "../utils/entity-configs.ts";
import type { TabKey } from "../utils/operations-tabs.ts";

interface Props {
  entity: string;
  action: "create" | "delete";
}

const EXECUTION_TAB: Record<string, TabKey> = {
  "courses:delete": "eliminar_cursos",
  "users:delete": "eliminar_usuarios",
  "categories:create": "crear_categorias",
  "categories:delete": "eliminar_categorias",
};

export default function CsvActionPage({ entity, action }: Props) {
  const config = ENTITY_CSV_CONFIGS[entity]?.[action];
  if (!config) return null;
  const executionTab = EXECUTION_TAB[`${entity}:${action}`];
  return (
    <Layout title={config.title}>
      <CsvUploader
        description={config.description}
        uploadEndpoint={config.endpoint}
        labelSingular={config.singular}
        labelPlural={config.plural}
        action={action}
        help={config.help}
      />
      {executionTab && <ExecutionButton tab={executionTab} />}
    </Layout>
  );
}
