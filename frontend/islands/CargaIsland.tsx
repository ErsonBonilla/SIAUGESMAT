// islands/CargaIsland.tsx
import FileUploader from "./SubirArchivoIsland.tsx";
import ExecutionButton from "../components/ExecutionButton.tsx";
import QueryHelp from "../components/QueryHelp.tsx";

export default function UploadIsland() {
  return (
    <div class="max-w-3xl mx-auto">
      <QueryHelp
        sections={[
          {
            title: "Qué hace el proceso",
            body:
              "Sincroniza con Moodle los cursos, categorías, usuarios y matriculaciones de docentes a partir del Excel de la carga académica.",
          },
          {
            title: "Archivo requerido",
            body:
              "Seleccione el archivo Excel (.xlsx o .xls) con los datos de la carga académica. Solo se admite un archivo por ejecución.",
          },
          {
            title: "Pasos",
            body: [
              "1. Seleccione el archivo Excel (.xlsx o .xls).",
              "2. Verifique el semestre (se detecta automáticamente según la fecha del servidor).",
              '3. Presione "Subir y procesar archivo".',
            ],
          },
          {
            title: "Qué se procesa (5 fases)",
            body: [
              "Fase 1 — Consulta: interpreta el Excel y consulta Moodle (categorías, cursos y usuarios).",
              "Fase 2 — Análisis: compara los cursos contra Moodle y define crear, eliminar, activar, ocultar o renombrar.",
              "Fase 3 — Estructura: aplica los cambios de cursos y categorías.",
              "Fase 4 — Usuarios: crea los usuarios nuevos y matricula a los docentes en sus cursos.",
              "Fase 5 — Reportes: genera CSVs, gráficos y un ZIP descargable.",
            ],
          },
          {
            title: "Notas",
            body: [
              "No se pueden subir archivos mientras haya un proceso en ejecución en la modalidad.",
              "Si el plan supera las 500 eliminaciones, la ejecución se pausa y requiere confirmación explícita.",
              "Una vez procesado, revise los resultados en el detalle de la ejecución y descargue los reportes.",
            ],
          },
        ]}
      />

      <FileUploader />
      <ExecutionButton tab="crear_cursos" />
    </div>
  );
}
