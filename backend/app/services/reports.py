"""
Servicio de generación de reportes (FASE 4 del Módulo de Novedades).

Genera archivos CSV estructurados a partir de los logs de ejecución
almacenados en ExecutionLog, documentando todas las incidencias y
operaciones realizadas durante el proceso ETL.
"""

import logging
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Execution, ExecutionLog
from app.services.report_utils import write_csv, create_zip, list_csv_files, get_csv_path

logger = logging.getLogger(__name__)


class ReportService:

    REPORT_NAMES = {
        "resumen_ejecutivo": "01_resumen_ejecutivo.csv",
        "inc_usuarios_inactivos": "02_inc_usuarios_inactivos.csv",
        "inc_cursos_recientes": "03_inc_cursos_recientes.csv",
        "inc_plantilla_no_encontrada": "04_inc_plantilla_no_encontrada.csv",
        "inc_correos_duplicados": "05_inc_correos_duplicados.csv",
        "audit_categorias_creadas": "06_audit_categorias_creadas.csv",
        "audit_cursos_creados": "07_audit_cursos_creados.csv",
        "audit_cursos_eliminados": "08_audit_cursos_eliminados.csv",
        "audit_cursos_ocultados": "09_audit_cursos_ocultados.csv",
        "audit_cursos_renombrados": "10_audit_cursos_renombrados.csv",
        "audit_cursos_activados": "11_audit_cursos_activados.csv",
        "audit_usuarios": "12_audit_usuarios.csv",
        "audit_matriculas": "13_audit_matriculas.csv",
        "audit_errores": "14_audit_errores.csv",
    }

    @classmethod
    def generate_all(cls, execution_id: int, db: Session) -> str:
        """
        Genera todos los reportes (CSV + gráficos Plotly) para una ejecución.

        Returns:
            Ruta al directorio donde se almacenaron los reportes.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(
            settings.REPORT_DIR, f"exec_{execution_id}_{timestamp}"
        )
        os.makedirs(report_dir, exist_ok=True)

        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        logs = (
            db.query(ExecutionLog)
            .filter(ExecutionLog.execution_id == execution_id)
            .all()
        )

        for cfg in cls.REPORT_CONFIGS:
            rows = []
            for log in logs:
                try:
                    if cfg["match"](log):
                        rows.append(cfg["extract"](log))
                except Exception:
                    logger.warning(f"Error extrayendo log para reporte {cfg.get('key', '?')}, log_id={log.id}")
            if rows:
                write_csv(
                    os.path.join(report_dir, cls.REPORT_NAMES[cfg["key"]]),
                    cfg["headers"],
                    rows,
                )
                logger.info(f"Reporte {cfg['key']}: {len(rows)} filas")
            else:
                logger.info(f"Reporte {cfg['key']}: sin datos, se omite")
        cls._write_audit_errores(report_dir, db, execution_id)
        cls._write_resumen_ejecutivo(report_dir, logs, execution)

        if execution:
            from app.services.charts import ChartService
            ChartService.generate_all(execution, logs, report_dir)

        create_zip(report_dir, report_dir + ".zip", extensions=(".csv", ".png", ".html"))
        cls._cleanup_old_reports(report_dir)

        logger.info(f"Reportes generados en: {report_dir}")
        return report_dir

    @classmethod
    def get_report_path(cls, report_dir: str, report_name: str) -> Optional[str]:
        filename = cls.REPORT_NAMES.get(report_name)
        if not filename:
            return None
        path = os.path.join(report_dir, filename)
        return path if os.path.exists(path) else None

    @classmethod
    def get_zip_path(cls, report_dir: str) -> Optional[str]:
        zip_path = report_dir + ".zip"
        return zip_path if os.path.exists(zip_path) else None

    @classmethod
    def list_reports(cls, report_dir: str) -> List[Dict[str, str]]:
        reports = []
        for name, filename in cls.REPORT_NAMES.items():
            path = os.path.join(report_dir, filename)
            if os.path.exists(path):
                reports.append({
                    "name": name,
                    "filename": filename,
                    "size": os.path.getsize(path),
                })
        return reports

    # ------------------------------------------------------------------
    # Configuración de reportes (data-driven)
    # ------------------------------------------------------------------
    REPORT_CONFIGS = [
        # INICIENCIAS —— 4 reportes
        {
            "key": "inc_usuarios_inactivos",
            "headers": ["Correo", "Curso (shortname)", "Curso (nombre)", "Motivo"],
            "match": lambda log: (
                log.action == "enrolment_failed" and log.detail
                and log.detail.get("reason") in ("user_not_found", "user_inactive")
            ),
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("course", ""),
                log.detail.get("fullname", ""),
                log.detail.get("reason", ""),
            ],
        },
        {
            "key": "inc_cursos_recientes",
            "headers": ["Shortname", "Curso", "Motivo", "Antigüedad (días)", "Profesor"],
            "match": lambda log: (
                log.action in ("alert_disappeared_recent", "alert_teacher_change_recent") and log.detail
            ),
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("fullname", ""),
                log.detail.get("reason", ""),
                str(round(log.detail.get("age_seconds", 0) / 86400, 1)),
                log.detail.get("professor", "") or log.detail.get("firstname", "") + " " + log.detail.get("lastname", ""),
            ],
        },
        {
            "key": "inc_plantilla_no_encontrada",
            "headers": ["Curso (shortname)", "Curso (nombre)", "Plantilla esperada", "Plantilla usada (fallback)"],
            "match": lambda log: log.action == "template_not_found" and log.detail,
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("fullname", ""),
                log.detail.get("template_shortname", ""),
                log.detail.get("fallback", ""),
            ],
        },
        {
            "key": "inc_correos_duplicados",
            "headers": ["Correo", "Usuarios encontrados", "Curso (shortname)", "Curso (nombre)"],
            "match": lambda log: log.action == "duplicate_email" and log.detail,
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("usernames", ""),
                log.detail.get("course", ""),
                log.detail.get("fullname", ""),
            ],
        },
        # AUDITORÍA — 10 reportes
        {
            "key": "audit_categorias_creadas",
            "headers": ["ID Number", "Nombre", "Padre"],
            "match": lambda log: log.action == "category_created",
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("name", ""),
                log.detail.get("parent", ""),
            ],
        },
        {
            "key": "audit_cursos_creados",
            "headers": ["Shortname", "Curso", "Categoría", "Profesor (username)", "Profesor (nombre)", "Acción", "Plantilla"],
            "match": lambda log: (
                log.action in ("course_created", "course_created_with_template", "course_recreated", "course_hidden_and_created")
                and log.detail
            ),
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("fullname", ""),
                log.detail.get("category_idnumber", ""),
                log.detail.get("professor", "") or log.detail.get("username", ""),
                f"{log.detail.get('firstname', '')} {log.detail.get('lastname', '')}".strip(),
                log.detail.get("reason", ""),
                log.detail.get("template_shortname", ""),
            ],
        },
        {
            "key": "audit_cursos_eliminados",
            "headers": ["Shortname", "Curso", "Motivo", "Antigüedad (días)"],
            "match": lambda log: log.action == "course_deleted",
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("fullname", ""),
                log.detail.get("reason", ""),
                str(round(log.detail.get("age_seconds", 0) / 86400, 1)),
            ],
        },
        {
            "key": "audit_cursos_ocultados",
            "headers": ["Shortname", "Curso", "Profesor (username)", "Profesor (nombre)"],
            "match": lambda log: log.action == "course_hidden",
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("fullname", ""),
                log.detail.get("professor", "") or log.detail.get("username", ""),
                f"{log.detail.get('firstname', '')} {log.detail.get('lastname', '')}".strip(),
            ],
        },
        {
            "key": "audit_cursos_renombrados",
            "headers": ["Shortname anterior", "Curso anterior", "Shortname nuevo", "Curso nuevo"],
            "match": lambda log: log.action == "course_renamed" and log.detail,
            "extract": lambda log: [
                log.detail.get("old_shortname", ""),
                log.detail.get("old_fullname", ""),
                log.identifier or "",
                log.detail.get("new_fullname", ""),
            ],
        },
        {
            "key": "audit_cursos_activados",
            "headers": ["Shortname", "Curso", "Profesor (username)", "Profesor (nombre)"],
            "match": lambda log: log.action == "course_activated",
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("fullname", ""),
                log.detail.get("professor", "") or log.detail.get("username", ""),
                f"{log.detail.get('firstname', '')} {log.detail.get('lastname', '')}".strip(),
            ],
        },
        {
            "key": "audit_usuarios",
            "headers": ["Username", "Nombre", "Apellido", "Email", "Estado"],
            "match": lambda log: log.action in ("user_created_createpassword", "user_resolved"),
            "extract": lambda log: [
                log.identifier or "",
                log.detail.get("firstname", ""),
                log.detail.get("lastname", ""),
                log.detail.get("email", ""),
                "Nuevo" if log.action == "user_created_createpassword" else "Existente",
            ],
        },
        {
            "key": "audit_matriculas",
            "headers": ["Curso (shortname)", "Curso (nombre)", "Usuario (username)", "Docente", "Resultado", "Motivo"],
            "match": lambda log: log.action in ("enrolment_ok", "enrolment_failed"),
            "extract": lambda log: [
                log.detail.get("course", ""),
                log.detail.get("fullname", ""),
                log.identifier or "",
                f"{log.detail.get('firstname', '')} {log.detail.get('lastname', '')}".strip(),
                "Éxito" if log.action == "enrolment_ok" else "Fallido",
                log.detail.get("reason", ""),
            ],
        },
        # Errores — desde ErrorLog (se procesa aparte en generate_all)
    ]

    @staticmethod
    def _cleanup_old_reports(current_dir: str, max_age_days: int = 90):
        """Elimina directorios y ZIPs de reportes más antiguos que max_age_days."""
        parent = os.path.dirname(current_dir)
        now = time.time()
        cutoff = now - (max_age_days * 86400)
        if not os.path.isdir(parent):
            return
        for entry in os.listdir(parent):
            path = os.path.join(parent, entry)
            # Limpiar directorios de reportes (exec_*) y sus ZIPs
            if entry.startswith("exec_") and os.path.isdir(path):
                if os.path.getmtime(path) < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
                    logger.info("Reportes antiguos eliminados: %s", path)
                    # También eliminar el ZIP si existe
                    zip_path = path + ".zip"
                    if os.path.exists(zip_path):
                        os.remove(zip_path)

    @classmethod
    def _write_resumen_ejecutivo(cls, report_dir: str, logs: List[ExecutionLog], execution=None):
        counts: Dict[str, int] = {}
        for log in logs:
            key = log.action
            counts[key] = counts.get(key, 0) + 1

        rows = []
        if execution:
            rows += [
                ["Semestre", execution.semester],
                ["Archivo", execution.filename],
                ["Duración (segundos)", str(round(execution.duration_seconds or 0))],
                ["Versión Moodle", execution.moodle_version or "-"],
                ["Modalidad", execution.modalidad or "-"],
                ["Errores totales (DB)", str(execution.errors_count or 0)],
            ]
        metric_rows = [
            ("Categorías creadas", "category_created"),
            ("Cursos creados", lambda c: c.get("course_created", 0) + c.get("course_created_with_template", 0)
             + c.get("course_recreated", 0) + c.get("course_hidden_and_created", 0)),
            ("Cursos eliminados", "course_deleted"),
            ("Cursos ocultados", "course_hidden"),
            ("Cursos renombrados", "course_renamed"),
            ("Cursos activados", "course_activated"),
            ("Usuarios nuevos", "user_created_createpassword"),
            ("Usuarios existentes (resueltos)", "user_resolved"),
            ("Matriculaciones exitosas", "enrolment_ok"),
            ("Matriculaciones fallidas", "enrolment_failed"),
            ("Plantillas no encontradas", "template_not_found"),
            ("Correos duplicados", "duplicate_email"),
            ("Alertas: cursos recientes", lambda c: c.get("alert_disappeared_recent", 0) + c.get("alert_teacher_change_recent", 0)),
        ]
        for label, src in metric_rows:
            val = src(counts) if callable(src) else counts.get(src, 0)
            if val > 0:
                rows.append([label, str(val)])
        # Tasa de error
        total_ops = sum(v for k, v in counts.items() if k.startswith("course_") or k.startswith("enrolment_"))
        total_errs = counts.get("enrolment_failed", 0)
        rate = round(total_errs / total_ops * 100, 1) if total_ops > 0 else 0
        rows.append(["Tasa de error (%)", str(rate)])

        write_csv(
            os.path.join(report_dir, cls.REPORT_NAMES["resumen_ejecutivo"]),
            ["Métrica", "Valor"],
            rows,
        )

    @classmethod
    def _write_audit_errores(cls, report_dir: str, db, execution_id: int):
        from app.db.models import ErrorLog
        errors = db.query(ErrorLog).filter(ErrorLog.execution_id == execution_id).all()
        if not errors:
            return
        rows = [[e.type, e.identifier or "", e.message or "", str(e.created_at)] for e in errors]
        write_csv(
            os.path.join(report_dir, cls.REPORT_NAMES["audit_errores"]),
            ["Fase/Tipo", "Identificador", "Mensaje", "Fecha"],
            rows,
        )
