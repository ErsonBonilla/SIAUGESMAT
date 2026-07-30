// utils/operations-tabs.ts
type TabComponent = "etl" | "batch";

export const OPERATIONS_TABS = [
  {
    key: "crear_cursos",
    label: "Crear Cursos",
    component: "etl" as TabComponent,
    entity: null,
    action: null,
  },
  {
    key: "crear_usuarios",
    label: "Crear Usuarios",
    component: "batch",
    entity: "users",
    action: "create",
  },
  {
    key: "crear_categorias",
    label: "Crear Categorías",
    component: "batch",
    entity: "categories",
    action: "create",
  },
  {
    key: "eliminar_cursos",
    label: "Eliminar Cursos",
    component: "batch",
    entity: "courses",
    action: "delete",
  },
  {
    key: "eliminar_usuarios",
    label: "Eliminar Usuarios",
    component: "batch",
    entity: "users",
    action: "delete",
  },
  {
    key: "eliminar_categorias",
    label: "Eliminar Categorías",
    component: "batch",
    entity: "categories",
    action: "delete",
  },
  {
    key: "visibilidad_cursos",
    label: "Visibilidad de Cursos",
    component: "batch",
    entity: "courses",
    action: "visibility",
  },
] as const;

export type TabKey = (typeof OPERATIONS_TABS)[number]["key"];
