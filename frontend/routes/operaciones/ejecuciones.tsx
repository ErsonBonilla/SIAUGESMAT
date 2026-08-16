import { requerirAutenticacion } from "../../utils/guarda-autenticacion.ts";
import Disposicion from "../../components/Disposicion.tsx";
import EjecucionesTabs from "../../islands/EjecucionesTabs.tsx";

export const handler = requerirAutenticacion();

export default function OperacionesPage() {
  return (
    <Disposicion title="Ejecuciones">
      <p
        class="text-sm text-[var(--text-secondary)] mt-1"
        style={{ marginTop: "-0.75rem", marginBottom: "1.5rem" }}
      >
        Historial de todas las ejecuciones del sistema.
      </p>
      <EjecucionesTabs />
    </Disposicion>
  );
}
