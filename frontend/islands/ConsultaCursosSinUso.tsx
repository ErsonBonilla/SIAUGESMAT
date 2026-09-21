import ConsultaInactivos, {
  type ColumnaInactivo,
} from "./ConsultaInactivos.tsx";

function formatearFecha(ts: number): string {
  if (!ts || ts <= 0) return "Nunca";
  return new Date(ts * 1000).toLocaleDateString();
}

function formatDaysSince(daysSince?: number): string {
  if (!daysSince || daysSince <= 0) return "—";
  return `${daysSince} d`;
}

const COLUMNAS: ColumnaInactivo[] = [
  {
    key: "shortname",
    label: "Shortname",
    destacar: true,
    render: (r) => String(r.shortname || "—"),
  },
  {
    key: "fullname",
    label: "Nombre",
    truncar: true,
    render: (r) => String(r.fullname ?? "—"),
  },
  {
    key: "categoryname",
    label: "Categoría",
    render: (r) => String(r.categoryname || "—"),
  },
  {
    key: "program",
    label: "Programa",
    render: (r) => String(r.program || "—"),
  },
  { key: "cat", label: "CAT", render: (r) => String(r.cat || "—") },
  {
    key: "timecreated",
    label: "Creado",
    render: (r) => formatearFecha(Number(r.timecreated)),
  },
  {
    key: "timemodified",
    label: "Última modificación",
    render: (r) => formatearFecha(Number(r.timemodified)),
  },
  {
    key: "days_since_modified",
    label: "Días sin uso",
    render: (r) => formatDaysSince(Number(r.days_since_modified)),
  },
];

export default function ConsultaCursosInactivos() {
  return (
    <ConsultaInactivos
      entity="inactive_courses"
      sustantivo="sin uso"
      columnas={COLUMNAS}
      nombreCsv="cursos_sin_uso.csv"
      textoVacio='Seleccione el corte (días, meses, años o semestre) y presione "Consultar".'
      seccionesAyuda={[
        {
          title: "Qué consulta",
          body:
            "Lista los cursos SIAUGESMAT que no se han modificado desde una fecha de corte, usando el campo timemodified (última modificación) de Moodle.",
        },
        {
          title: "Cómo elegir el corte",
          body: [
            "Por días (1-30), meses (1-12), años (≥ 1) o semestre (ej. 2026A).",
            "El corte define la fecha límite: solo se muestran cursos cuya última modificación es anterior a esa fecha.",
          ],
        },
        {
          title: "Resultado",
          body: [
            "Cada fila muestra shortname, nombre, categoría, programa, CAT, fecha de creación, última modificación y días sin uso.",
          ],
        },
      ]}
    />
  );
}
