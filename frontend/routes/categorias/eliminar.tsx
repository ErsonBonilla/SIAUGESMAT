import { requireAuth } from "../../utils/auth-guard.ts";
import CsvActionPage from "../../components/CsvActionPage.tsx";

export const handler = requireAuth();

export default function EliminarCategoriasPage() {
  return <CsvActionPage entity="categories" action="delete" />;
}
