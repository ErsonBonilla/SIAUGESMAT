import type { Column, Filter } from "../islands/TablaConsultaIsland.tsx";
import type { QueryHelpSection } from "../components/QueryHelp.tsx";

interface EntityConfig {
  title: string;
  searchPlaceholder: string;
  columns: Column[];
  filters?: Filter[];
  help?: QueryHelpSection[];
}

export const ENTITY_CONSULT_CONFIGS: Record<string, EntityConfig> = {
  categories: {
    title: "Categorías",
    searchPlaceholder: "Buscar por idnumber...",
    columns: [
      { key: "id", label: "ID" },
      { key: "idnumber", label: "ID Number" },
      { key: "name", label: "Nombre" },
      { key: "parent", label: "Padre" },
      { key: "coursecount", label: "Cursos" },
    ],
    help: [
      {
        title: "Qué valor buscar",
        body: [
          'El idnumber es el identificador de la categoría, por ejemplo "DISTANCIA" o "IDEAD".',
          "La búsqueda es de coincidencia exacta: debe escribirse el idnumber completo.",
          "Las columnas del resultado muestran: ID, ID Number, nombre, categoría padre y cantidad de cursos.",
        ],
      },
    ],
  },
  courses: {
    title: "Cursos",
    searchPlaceholder: "Buscar por shortname...",
    filters: [
      {
        key: "status",
        label: "Estado",
        type: "select",
        options: [
          { value: "all", label: "Todos los cursos" },
          { value: "orphan", label: "Cursos Huérfanos" },
        ],
      },
      {
        key: "pattern",
        label: "Formato de código",
        type: "select",
        options: [
          { value: "all", label: "Todos los códigos" },
          {
            value: "6segments",
            label: "6 segmentos (CAL_0852_sIV_5031216_G-1_29114506)",
          },
          {
            value: "5segments",
            label: "5 segmentos (CHA_0845_sVI_102131_G-1)",
          },
        ],
      },
    ],
    columns: [
      { key: "id", label: "ID" },
      { key: "shortname", label: "Shortname" },
      { key: "fullname", label: "Nombre completo" },
      { key: "categoryname", label: "Categoría" },
      { key: "visible", label: "Visible", renderKey: "yesNo" },
    ],
    help: [
      {
        title: "Qué valor buscar",
        body: [
          "El shortname es el código corto del curso, por ejemplo CAL_0852_sIV_5031216_G-1_29114506.",
          'La búsqueda es parcial: escribiendo una parte del código (ej. "0852", "CAL_" o "5031216") se muestran todos los cursos que la contengan. No distingue mayúsculas.',
        ],
      },
      {
        title: "Filtro Estado",
        body: [
          "Todos los cursos: devuelve todos los cursos de Moodle.",
          "Cursos huérfanos: solo los cursos SIAUGESMAT sin docentes matriculados. Esta opción revisa los docentes de cada curso, por lo que puede tardar.",
        ],
      },
      {
        title: "Filtro Formato de código",
        body: [
          "6 segmentos: códigos que incluyen la cédula del profesor, como CAL_0852_sIV_5031216_G-1_29114506.",
          "5 segmentos: códigos sin cédula, como CHA_0845_sVI_102131_G-1.",
        ],
      },
    ],
  },
  users: {
    title: "Usuarios",
    searchPlaceholder:
      "Buscar por username, email o nombre (coincidencia exacta)...",
    filters: [
      {
        key: "status",
        label: "Filtro adicional",
        type: "select",
        options: [
          { value: "", label: "Sin filtro adicional" },
          { value: "never_logged_in", label: "Nunca ingresaron" },
        ],
      },
    ],
    columns: [
      { key: "username", label: "Username" },
      { key: "email", label: "Email" },
      { key: "firstname", label: "Nombres" },
      { key: "lastname", label: "Apellidos" },
      {
        key: "lastlogin",
        label: "Último login",
        renderKey: "lastlogin",
      },
    ],
    help: [
      {
        title: "Qué valor buscar",
        body: [
          "Podés buscar por username, email, nombre (firstname) o apellido (lastname).",
          'La búsqueda es de coincidencia exacta: escribí el valor completo de uno de esos campos. Por ejemplo "jtorrespr", "jtorrespr@ut.edu.co", "Jamer" o "Torres".',
          "El webservice de Moodle 3.9 no permite búsquedas parciales ni listar todos los usuarios, por lo que no se admiten fragmentos.",
        ],
      },
      {
        title: "Filtro adicional",
        body: [
          "Nunca ingresaron: muestra solo los usuarios que nunca iniciaron sesión en Moodle (último login vacío).",
        ],
      },
    ],
  },
};

interface CsvActionConfig {
  title: string;
  description: string;
  endpoint: string;
  singular: string;
  plural: string;
  help?: QueryHelpSection[];
}

export const ENTITY_CSV_CONFIGS: Record<
  string,
  Record<string, CsvActionConfig>
> = {
  categories: {
    create: {
      title: "Crear categorías",
      description:
        "Subí un archivo CSV con la columna 'name' (obligatoria) y opcionalmente 'idnumber', 'parent', 'description' y 'visible'. Las categorías se crean en árbol bajo 'IDEAD' (idnumber: DISTANCIA).",
      endpoint: "categories/create-csv",
      singular: "categoría",
      plural: "categorías",
      help: [
        {
          title: "Archivo CSV requerido",
          body: [
            "Columna obligatoria: name (nombre de la categoría).",
            "Columnas opcionales: idnumber, parent, description y visible.",
          ],
        },
        {
          title: "Dónde se crean",
          body:
            "Las categorías se crean en árbol bajo 'IDEAD' (idnumber: DISTANCIA).",
        },
      ],
    },
    delete: {
      title: "Eliminar categorías",
      description:
        "Subí un archivo CSV con la columna 'idnumber' que contenga los identificadores de las categorías a eliminar.",
      endpoint: "categories/upload-csv",
      singular: "categoría",
      plural: "categorías",
      help: [
        {
          title: "Archivo CSV requerido",
          body:
            "Columna obligatoria: idnumber (identificador de cada categoría a eliminar).",
        },
      ],
    },
  },
  courses: {
    delete: {
      title: "Eliminar cursos",
      description:
        "Subí un archivo CSV con la columna 'shortname' que contenga los nombres cortos de los cursos a eliminar.",
      endpoint: "courses/upload-csv",
      singular: "curso",
      plural: "cursos",
      help: [
        {
          title: "Archivo CSV requerido",
          body:
            "Columna obligatoria: shortname (código corto de cada curso a eliminar).",
        },
      ],
    },
  },
  users: {
    delete: {
      title: "Eliminar usuarios",
      description:
        "Subí un archivo CSV con la columna 'username' que contenga los nombres de usuario a eliminar.",
      endpoint: "users/upload-csv",
      singular: "usuario",
      plural: "usuarios",
      help: [
        {
          title: "Archivo CSV requerido",
          body:
            "Columna obligatoria: username (nombre de usuario de cada cuenta a eliminar).",
        },
      ],
    },
  },
};
