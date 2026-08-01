export const REPORT_LABELS: Record<string, string> = {
  resumen_ejecutivo: "Resumen ejecutivo",
  inc_usuarios_inactivos: "Incidencias: Usuarios inactivos",
  inc_cursos_recientes: "Incidencias: Cursos recientes",
  inc_plantilla_no_encontrada: "Incidencias: Plantillas no encontradas",
  inc_correos_duplicados: "Incidencias: Correos duplicados",
  audit_categorias_creadas: "Auditoría: Categorías creadas",
  audit_cursos_creados: "Auditoría: Cursos creados",
  audit_cursos_eliminados: "Auditoría: Cursos eliminados",
  audit_cursos_ocultados: "Auditoría: Cursos ocultados",
  audit_cursos_renombrados: "Auditoría: Cursos renombrados",
  audit_cursos_activados: "Auditoría: Cursos activados",
  audit_usuarios: "Auditoría: Usuarios (nuevos y existentes)",
  audit_matriculas: "Auditoría: Matrículas (exitosas y fallidas)",
  audit_conflictos_identidad: "Auditoría: Conflictos de identidad",
  audit_plan_acciones: "Auditoría: Plan de acciones",
  audit_errores: "Auditoría: Errores del proceso",
};

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
