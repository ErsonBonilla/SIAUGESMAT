import Layout from "./Layout.tsx";
import TablaConsultaIsland from "../islands/TablaConsultaIsland.tsx";
import { ENTITY_CONSULT_CONFIGS } from "../utils/entity-configs.ts";

interface Props {
  entity: string;
}

export default function ConsultPage({ entity }: Props) {
  const config = ENTITY_CONSULT_CONFIGS[entity];
  if (!config) return null;
  return (
    <Layout title={config.title}>
      <TablaConsultaIsland entity={entity} {...config} />
    </Layout>
  );
}
