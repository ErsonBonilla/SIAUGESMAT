import { useComputed, useSignal } from "@preact/signals";
import {
  descargarReporte,
  obtenerUrlExportarConsulta,
} from "../services/api.ts";
import { useConsultaTarea } from "../hooks/useConsultaTarea.ts";
import { IconoDescargar, IconoSpinner } from "../utils/iconos.tsx";
import CajaError from "../components/CajaError.tsx";
import Paginacion from "../components/Paginacion.tsx";
import AyudaConsulta from "../components/AyudaConsulta.tsx";

const PAGE_SIZE = 20;

const COLUMNS = [
  { key: "email", label: "Correo" },
  { key: "username", label: "Username" },
  { key: "firstname", label: "Nombres" },
  { key: "lastname", label: "Apellidos" },
  { key: "user_id", label: "ID Moodle" },
  { key: "duplicate_count", label: "Nº de cuentas" },
];

interface FilaCorreoDuplicado {
  email: string;
  username: string;
  firstname: string;
  lastname: string;
  user_id: number | string;
  duplicate_count: number;
}

export default function ConsultaCorreosDuplicados() {
  const { data, loading, error, taskId, taskStatus, iniciarConsulta } =
    useConsultaTarea<FilaCorreoDuplicado>();
  const pageOffset = useSignal(0);
  const totalItems = useComputed(() => data.value.length);
  const pageData = useComputed(() =>
    data.value.slice(pageOffset.value, pageOffset.value + PAGE_SIZE)
  );

  const startQuery = async () => {
    pageOffset.value = 0;
    await iniciarConsulta("duplicate_emails", {});
  };

  const exportUrl = taskId.value
    ? obtenerUrlExportarConsulta(taskId.value)
    : "";

  return (
    <div class="space-y-4">
      <AyudaConsulta
        sections={[
          {
            title: "Qué consulta",
            body:
              "Lista los correos que tienen más de un usuario registrado con ese correo en Moodle. Cada fila es una cuenta que comparte un correo duplicado.",
          },
          {
            title: "Cómo se encuentra la información",
            body: [
              "Moodle 3.9 no permite listar todos los usuarios por API, por lo que la consulta combina dos fuentes: los usuarios que la app ha creado o matriculado y los matriculados en cursos SIAUGESMAT.",
              "Luego re-consulta cada correo candidato en Moodle para capturar TODAS las cuentas que lo comparten, incluidas las que la app nunca procesó.",
              "La columna 'Nº de cuentas' indica cuántas cuentas comparten ese correo.",
            ],
          },
          {
            title: "Tiempo de ejecución",
            body: [
              "Esta consulta recorre todos los cursos SIAUGESMAT y puede tardar entre 15 y 25 minutos.",
            ],
          },
        ]}
      />

      <button
        type="button"
        onClick={startQuery}
        disabled={loading.value}
        class="px-4 py-1.5 bg-[var(--brand-green)] text-white rounded text-sm hover:brightness-90 disabled:opacity-60"
      >
        {loading.value
          ? (
            <span class="flex items-center gap-1.5">
              <IconoSpinner class="animate-spin h-4 w-4" />
              Consultando...
            </span>
          )
          : "Consultar"}
      </button>

      {loading.value && taskStatus.value?.status === "running" && (
        <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <IconoSpinner class="animate-spin h-4 w-4" />
          <span>
            Consultando Moodle (procesando {taskStatus.value?.total_count || 0}
            {" "}
            ítems)... puede tardar varios minutos.
          </span>
        </div>
      )}

      {error.value && <CajaError message={error.value} />}

      {!loading.value && !error.value && data.value.length > 0 && (
        <div class="flex items-center justify-between">
          <span class="text-xs text-[var(--text-secondary)]">
            {pageOffset.value + 1}–{Math.min(
              pageOffset.value + PAGE_SIZE,
              totalItems.value,
            )} de {totalItems.value}{" "}
            resultado{totalItems.value !== 1 ? "s" : ""}
          </span>
          {exportUrl && (
            <button
              type="button"
              onClick={() =>
                descargarReporte(exportUrl, "correos_duplicados.csv").catch(
                  () => {},
                )}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-tertiary)] text-[var(--text-primary)] rounded text-sm font-medium no-underline hover:bg-[var(--border-secondary)] transition cursor-pointer"
            >
              <IconoDescargar class="w-4 h-4" />
              CSV
            </button>
          )}
        </div>
      )}

      {!loading.value && !error.value && (
        <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border-primary)]">
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    class="text-left py-3 px-3 font-medium text-[var(--text-secondary)]"
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.value.length === 0
                ? (
                  <tr>
                    <td
                      colSpan={COLUMNS.length}
                      class="py-12 text-center text-[var(--text-muted)]"
                    >
                      {taskStatus.value !== null
                        ? "No se encontraron correos duplicados."
                        : 'Presione "Consultar" para buscar correos con más de un usuario.'}
                    </td>
                  </tr>
                )
                : pageData.value.map((row, idx) => (
                  <tr
                    key={idx}
                    class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
                  >
                    <td class="py-2 px-3 text-[var(--text-primary)] font-medium">
                      {row.email}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.username}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.firstname || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.lastname || "—"}
                    </td>
                    <td class="py-2 px-3 text-[var(--text-primary)]">
                      {row.user_id}
                    </td>
                    <td class="py-2 px-3">
                      <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--brand-red)]/10 text-[var(--brand-red)]">
                        {row.duplicate_count}
                      </span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading.value && !error.value && data.value.length > PAGE_SIZE && (
        <Paginacion
          offset={pageOffset.value}
          tamanoPagina={PAGE_SIZE}
          total={totalItems.value}
          label="resultados"
          alCambiarPagina={(o) => {
            pageOffset.value = o;
          }}
        />
      )}
    </div>
  );
}
