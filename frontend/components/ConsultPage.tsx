import Layout from "./Layout.tsx";
import QueryTable from "../islands/QueryTable.tsx";
import { ENTITY_CONSULT_CONFIGS } from "../utils/entity-configs.ts";

interface Props {
  entity: string;
}

export default function ConsultPage({ entity }: Props) {
  const config = ENTITY_CONSULT_CONFIGS[entity];
  if (!config) return null;
  return (
    <Layout title={config.title}>
      <QueryTable entity={entity} {...config} />
    </Layout>
  );
}
