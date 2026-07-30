import { requireAuth } from "../../utils/auth-guard.ts";
import CsvActionPage from "../../components/CsvActionPage.tsx";

export const handler = requireAuth();

export default function EliminarCursosPage() {
  return <CsvActionPage entity="courses" action="delete" />;
}
