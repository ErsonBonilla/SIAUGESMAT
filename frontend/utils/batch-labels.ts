// utils/batch-labels.ts

export const BATCH_ENTITY_LABELS: Record<string, string> = {
  courses: "Cursos",
  categories: "Categorías",
  users: "Usuarios",
};

export const BATCH_ACTION_LABELS: Record<string, string> = {
  create: "Creación",
  delete: "Eliminación",
  visibility: "Visibilidad",
};

export function batchEntityLabel(entity: string | null | undefined): string {
  if (!entity) return "—";
  return BATCH_ENTITY_LABELS[entity] ?? entity;
}

export function batchActionLabel(action: string | null | undefined): string {
  if (!action) return "—";
  return BATCH_ACTION_LABELS[action] ?? action;
}
