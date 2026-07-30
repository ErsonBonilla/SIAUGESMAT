import { requireAuth } from "../../utils/auth-guard.ts";
import CsvActionPage from "../../components/CsvActionPage.tsx";

export const handler = requireAuth();

export default function CrearCategoriasPage() {
  return <CsvActionPage entity="categories" action="create" />;
}
