import { requireAuth } from "../../utils/auth-guard.ts";
import ConsultPage from "../../components/ConsultPage.tsx";

export const handler = requireAuth();

export default function ConsultasCursosPage() {
  return <ConsultPage entity="courses" />;
}
