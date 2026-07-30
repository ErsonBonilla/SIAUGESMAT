// islands/UploadIsland.tsx
import FileUploader from "./FileUploader.tsx";

export default function UploadIsland() {
  return (
    <div class="max-w-3xl mx-auto">
      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6 mb-6 text-[var(--text-primary)]">
        <h2 class="text-lg font-semibold mb-3 text-[var(--text-primary)]">
          Instrucciones
        </h2>
        <ul class="list-disc list-inside text-sm text-[var(--text-secondary)] flex flex-col gap-1">
          <li>
            Seleccione el archivo Excel (.xlsx) con los datos de la carga
            académica.
          </li>
          <li>
            El{" "}
            <strong class="text-[var(--brand-red)]">semestre académico</strong>
            {" "}
            se detecta automáticamente según la fecha del servidor.
          </li>
          <li>
            El archivo se procesa completo:{" "}
            <span class="text-[var(--brand-red)] font-medium">cursos</span>,
            {" "}
            <span class="text-[var(--accent)] font-medium">usuarios</span> y
            {" "}
            <span class="text-[#7C3AED] font-medium">
              matriculación de profesores
            </span>.
          </li>
          <li>
            Una vez procesado, podrá revisar los resultados en el histórico o en
            el detalle de la ejecución.
          </li>
        </ul>
      </div>

      <FileUploader />
    </div>
  );
}
