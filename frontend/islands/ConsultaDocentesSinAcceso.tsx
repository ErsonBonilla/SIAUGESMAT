import ConsultaInactivos, {
  type ColumnaInactivo,
} from "./ConsultaInactivos.tsx";

function formatLastAccess(ts: number): string {
  if (!ts || ts <= 0) return "Nunca";
  return new Date(ts * 1000).toLocaleString();
}

function formatDaysSince(daysSince?: number): string {
  if (!daysSince || daysSince <= 0) return "Nunca";
  return `${daysSince} d`;
}

const COLUMNAS: ColumnaInactivo[] = [
  {
    key: "teacher_name",
    label: "Docente",
    destacar: true,
    render: (r) => String(r.teacher_name || "—"),
  },
  {
    key: "username",
    label: "Username",
    render: (r) => String(r.username ?? "—"),
  },
  { key: "email", label: "Correo", render: (r) => String(r.email ?? "—") },
  {
    key: "course_name",
    label: "Curso",
    truncar: true,
    render: (r) => String(r.course_name ?? "—"),
  },
  {
    key: "program",
    label: "Programa",
    render: (r) => String(r.program || "—"),
  },
  { key: "cat", label: "CAT", render: (r) => String(r.cat || "—") },
  {
    key: "last_access",
    label: "Último acceso",
    render: (r) => formatLastAccess(Number(r.last_access)),
  },
  {
    key: "days_since_last_access",
    label: "Días sin acceso",
    render: (r) => formatDaysSince(Number(r.days_since_last_access)),
  },
];

export default function ConsultaDocentesInactivos() {
  return (
    <ConsultaInactivos
      entity="inactive_teachers"
      sustantivo="sin acceso"
      columnas={COLUMNAS}
      nombreCsv="docentes_inactivos.csv"
      textoVacio='Seleccione el corte (días o semestre) y presione "Consultar".'
      seccionesAyuda={[
        {
          title: "Qué consulta",
          body:
            "Lista los docentes (rol editingteacher) que no han accedido a sus cursos SIAUGESMAT desde una fecha de corte, usando el campo lastcourseaccess de Moodle.",
        },
        {
          title: "Cómo elegir el corte",
          body: [
            "Por días (1-30, por defecto 15), meses (1-12), años (≥ 1) o semestre (ej. 2026A).",
            "El corte define la fecha límite: se muestran docentes cuyo último acceso al curso es anterior a esa fecha.",
          ],
        },
        {
          title: "Resultado",
          body: [
            "Cada fila muestra nombre del docente, username, correo, curso, programa, CAT, último acceso y días sin acceso.",
            "Esta consulta recorre todos los cursos SIAUGESMAT y puede tardar varios minutos.",
          ],
        },
      ]}
    />
  );
}
