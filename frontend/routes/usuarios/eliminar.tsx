import { requireAuth } from "../../utils/auth-guard.ts";
import CsvActionPage from "../../components/CsvActionPage.tsx";

export const handler = requireAuth();

export default function EliminarUsuariosPage() {
  return <CsvActionPage entity="users" action="delete" />;
}
