// utils/batch-labels.ts

export const ETIQUETAS_ENTIDADES_LOTE: Record<string, string> = {
  courses: "Cursos",
  categories: "Categorías",
  users: "Usuarios",
};

export const ETIQUETAS_ACCIONES_LOTE: Record<string, string> = {
  create: "Creación",
  delete: "Eliminación",
  visibility: "Visibilidad",
};

export function etiquetaEntidadLote(entity: string | null | undefined): string {
  if (!entity) return "—";
  return ETIQUETAS_ENTIDADES_LOTE[entity] ?? entity;
}

export function etiquetaAccionLote(action: string | null | undefined): string {
  if (!action) return "—";
  return ETIQUETAS_ACCIONES_LOTE[action] ?? action;
}
