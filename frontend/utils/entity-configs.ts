import type { Column, Filter } from "../islands/QueryTable.tsx";

interface EntityConfig {
  title: string;
  searchPlaceholder: string;
  columns: Column[];
  filters?: Filter[];
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
          { value: "unused_6months", label: "Sin uso (> 6 meses)" },
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
      { key: "visible", label: "Visible", render: (v) => v == 1 ? "Sí" : "No" },
    ],
  },
  users: {
    title: "Usuarios",
    searchPlaceholder: "Buscar por username o email...",
    filters: [
      {
        key: "role",
        label: "Rol",
        type: "select",
        options: [
          { value: "all", label: "Todos los usuarios" },
          { value: "professor", label: "Profesores (editingteacher)" },
        ],
      },
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
        render: (v) =>
          typeof v === "number" && v > 0
            ? new Date(v * 1000).toLocaleString()
            : "Nunca",
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
    },
    delete: {
      title: "Eliminar categorías",
      description:
        "Subí un archivo CSV con la columna 'idnumber' que contenga los identificadores de las categorías a eliminar.",
      endpoint: "categories/upload-csv",
      singular: "categoría",
      plural: "categorías",
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
    },
  },
};
