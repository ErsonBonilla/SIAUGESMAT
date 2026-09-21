// routes/reportes.tsx
import type { PageProps } from "@fresh/core";
import { requerirAutenticacion } from "../utils/guarda-autenticacion.ts";
import Disposicion from "../components/Disposicion.tsx";
import ReportesIsland from "../islands/Reportes.tsx";

export const handler = requerirAutenticacion();

export default function PaginaReportes({ url }: PageProps) {
  const executionId = parseInt(url.searchParams.get("execution_id") || "0");

  if (!executionId) {
    return (
      <Disposicion title="Reportes">
        <p class="text-[var(--text-secondary)] text-sm">
          Seleccione una ejecución desde{" "}
          <a
            href="/operaciones/ejecuciones"
            class="text-[var(--accent)] hover:underline"
          >
            el listado de ejecuciones
          </a>{" "}
          para ver sus gráficos y descargar reportes.
        </p>
      </Disposicion>
    );
  }

  return (
    <Disposicion title={`Reportes - Ejecución #${executionId}`}>
      <ReportesIsland executionId={executionId} />
    </Disposicion>
  );
}
