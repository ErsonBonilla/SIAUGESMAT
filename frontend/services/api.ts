// services/api.ts — barrel (split: tipos, nucleo, autenticacion, trabajos, analitica, reportes, operaciones, consultas)
export {
  cerrarSesion,
  iniciarSesion,
  obtenerMiPerfil,
} from "./api/autenticacion.ts";

export {
  cancelarEjecucion,
  confirmarEjecucion,
  eliminarEjecucion,
  type EstadoSubida,
  iniciarProceso,
  listarEjecuciones,
  obtenerEjecucion,
  obtenerErroresEjecucion,
  obtenerEstadoSubida,
  obtenerSemestreActual,
  pausarEjecucion,
  reanudarEjecucion,
  subirArchivo,
} from "./api/trabajos.ts";

export {
  listarGraficos,
  obtenerDatosGrafico,
  obtenerHistorial,
  obtenerReciente,
  obtenerSemaforo,
} from "./api/analitica.ts";

export {
  descargarReporte,
  listarReportes,
  obtenerUrlArchivoReporte,
  obtenerUrlDescargaReporte,
} from "./api/reportes.ts";

export {
  cancelarLote,
  eliminarLote,
  listarLotes,
  obtenerAnaliticaOperaciones,
  obtenerEstadoLote,
  obtenerUrlArchivoReporteLote,
  obtenerUrlDescargaReporteLote,
  pausarLote,
  reanudarLote,
  subirArchivoCsv,
} from "./api/operaciones.ts";

export { subirCsvVisibilidad } from "./api/mantenimiento.ts";

export {
  consultarEntidades,
  obtenerEstadoTareaConsulta,
  obtenerUrlExportarConsulta,
} from "./api/consultas.ts";

export { compararNovedades } from "./api/novedades.ts";

export type {
  DisposicionTrazasGrafico,
  Ejecucion,
  EjecucionReciente,
  EstadoLoteOperacion,
  EstadoSemaforo,
  EstadoTareaConsulta,
  FilaCursoInactivo,
  FilaDocenteInactivo,
  InfoGrafico,
  InfoReporte,
  ItemHistorialOperaciones,
  ItemNovedad,
  ItemOperacionSalida,
  LoteOperacionSalida,
  MetricasSemestre,
  PerfilUsuario,
  RegistroError,
  RespuestaListaGraficos,
  RespuestaListaReportes,
  RespuestaNovedades,
  RespuestaSubidaCsv,
} from "./api/tipos.ts";
