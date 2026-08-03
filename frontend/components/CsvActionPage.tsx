import Layout from "./Layout.tsx";
import CsvUploader from "../islands/CsvUploader.tsx";
import { ENTITY_CSV_CONFIGS } from "../utils/entity-configs.ts";

interface Props {
  entity: string;
  action: "create" | "delete";
}

export default function CsvActionPage({ entity, action }: Props) {
  const config = ENTITY_CSV_CONFIGS[entity]?.[action];
  if (!config) return null;
  return (
    <Layout title={config.title}>
      <CsvUploader
        description={config.description}
        uploadEndpoint={config.endpoint}
        labelSingular={config.singular}
        labelPlural={config.plural}
        action={action}
      />
    </Layout>
  );
}
