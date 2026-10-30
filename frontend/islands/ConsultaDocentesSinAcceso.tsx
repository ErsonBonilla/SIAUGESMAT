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
    key: "cat_shortname",
    label: "Shortname CAT",
    render: (r) => String(r.cat_shortname || r.cat_prefix || "—"),
  },
  {
    key: "cat_name",
    label: "Nombre CAT",
    render: (r) => String(r.cat_name || r.cat || "—"),
  },
  {
    key: "semester_shortname",
    label: "Shortname Semestre",
    render: (r) => String(r.semester_shortname || "—"),
  },
  {
    key: "semester_name",
    label: "Nombre Semestre",
    render: (r) => String(r.semester_name || "—"),
  },
  {
    key: "program_shortname",
    label: "Shortname Programa",
    render: (r) => String(r.program_shortname || r.program || "—"),
  },
  {
    key: "program_name",
    label: "Nombre Programa",
    truncar: true,
    render: (r) => String(r.program_name || r.program || "—"),
  },
  {
    key: "course_shortname",
    label: "Shortname Curso",
    render: (r) => String(r.course_shortname || "—"),
  },
  {
    key: "course_name",
    label: "Curso",
    truncar: true,
    render: (r) => String(r.course_name ?? "—"),
  },
  {
    key: "username",
    label: "Username",
    destacar: true,
    render: (r) => String(r.username ?? "—"),
  },
  {
    key: "teacher_name",
    label: "Docente",
    render: (r) => String(r.teacher_name || "—"),
  },
  { key: "email", label: "Email", render: (r) => String(r.email ?? "—") },
  {
    key: "last_access",
    label: "Fecha último acceso",
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
      modosPermitidos={["days", "months", "years"]}
      textoVacio='Seleccione el tiempo (días, meses o años) y presione "Consultar".'
      seccionesAyuda={[
        {
          title: "Qué consulta",
          body:
            "Lista los docentes (rol editingteacher) que no han accedido a sus cursos visibles bajo la categoría IDEAD desde una fecha de corte, usando el campo lastcourseaccess de Moodle. Excluye cursos ocultos.",
        },
        {
          title: "Cómo elegir el tiempo",
          body: [
            "Por días (1-30, por defecto 15), meses (1-12) o años (≥ 1).",
            "El corte define la fecha límite: se muestran docentes cuyo último acceso al curso es anterior a esa fecha (o que nunca han ingresado).",
          ],
        },
        {
          title: "Resultado",
          body: [
            "Cada fila incluye las subcategorías bajo IDEAD (shortname y nombre de CAT, semestre y programa académico), el curso, username, nombre completo y email del docente, fecha del último acceso y días sin acceder al curso.",
            "Esta consulta recorre los cursos visibles de IDEAD y puede tardar varios minutos.",
          ],
        },
      ]}
    />
  );
}
