export const REPORT_LABELS: Record<string, string> = {
  inc_usuarios_inactivos: "Usuarios inactivos",
  inc_correo_no_institucional: "Correos no institucionales",
  inc_cursos_recientes: "Cursos con cambios recientes",
  inc_plantilla_no_encontrada: "Plantillas no encontradas",
  inc_correos_duplicados: "Correos duplicados",
  audit_categorias_creadas: "Categorías creadas",
  audit_cursos_creados: "Cursos creados",
  audit_cursos_eliminados: "Cursos eliminados",
  audit_cursos_cambio_grupo: "Cursos con cambio de grupo",
  audit_cursos_activados: "Cursos activados",
  audit_usuarios_creados: "Usuarios creados",
  audit_usuarios_createpassword: "Usuarios con password inicial",
  resumen_ejecutivo: "Resumen ejecutivo",
};

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
