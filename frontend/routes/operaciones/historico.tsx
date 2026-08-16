import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import HistoricoTabs from "../../islands/HistoricoTabs.tsx";

export const handler = requerirAutenticacion();

export default function HistoricoPage() {
  return (
    <Disposicion title="Histórico de operaciones">
      <p
        class="text-sm text-[var(--text-secondary)] mt-1"
        style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}
      >
        Métricas históricas de todas las operaciones del sistema.
      </p>
      <HistoricoTabs />
    </Disposicion>
  );
}
