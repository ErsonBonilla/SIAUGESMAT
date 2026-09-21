"""renombrar tablas y columnas a espanol

Renombra todas las tablas, columnas, índices y restricciones de la base de
datos a sus equivalentes en español, alineándolas con los modelos ORM
actualizados en `app.db.models`.

Revision ID: a1b2c3d4e5f6
Revises: 928546730563
Create Date: 2026-08-13 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "928546730563"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_columns(table: str, renames: list[tuple[str, str]]) -> None:
    """Renombra columnas de una tabla de forma segura (PostgreSQL)."""
    for old, new in renames:
        op.alter_column(table, old, new_column_name=new)


def _rename_index(indexes: list[tuple[str, str]]) -> None:
    """Renombra índices solo si existen (defensivo ante linajes distintos)."""
    offline = context.is_offline_mode()
    for old, new in indexes:
        if offline:
            op.execute(f"ALTER INDEX {old} RENAME TO {new}")
            continue
        conn = op.get_bind()
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"), {"n": old}
        ).scalar()
        if exists:
            op.execute(f"ALTER INDEX {old} RENAME TO {new}")


def _rename_constraint(table: str, renames: list[tuple[str, str]]) -> None:
    """Renombra constraints solo si existen (defensivo ante linajes distintos)."""
    offline = context.is_offline_mode()
    for old, new in renames:
        if offline:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")
            continue
        conn = op.get_bind()
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = :n "
                "AND connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')"
            ),
            {"n": old},
        ).scalar()
        if exists:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # executions -> ejecuciones
    # ------------------------------------------------------------------
    op.rename_table("executions", "ejecuciones")
    _rename_columns(
        "ejecuciones",
        [
            ("filename", "nombre_archivo"),
            ("semester", "semestre"),
            ("mode", "modo"),
            ("status", "estado"),
            ("metrics", "metricas"),
            ("errors_count", "conteo_errores"),
            ("report_dir", "directorio_reporte"),
            ("started_at", "iniciado_en"),
            ("completed_at", "completado_en"),
            ("duration_seconds", "duracion_segundos"),
            ("current_phase", "fase_actual"),
            ("progress_pct", "porcentaje_progreso"),
            ("progress_updated_at", "progreso_actualizado_en"),
            ("current_step", "paso_actual"),
            ("moodle_version", "version_moodle"),
            ("phase_checkpoint", "checkpoint_fase"),
            ("celery_task_id", "id_tarea_celery"),
            ("created_at", "creado_en"),
        ],
    )
    _rename_index(
        [
            ("ix_executions_id", "ix_ejecuciones_id"),
            ("ix_executions_created_at", "ix_ejecuciones_creado_en"),
            ("ix_executions_semester", "ix_ejecuciones_semestre"),
            ("ix_executions_status", "ix_ejecuciones_estado"),
            ("ix_executions_modalidad", "ix_ejecuciones_modalidad"),
            ("ix_executions_celery_task_id", "ix_ejecuciones_id_tarea_celery"),
        ]
    )

    # ------------------------------------------------------------------
    # error_logs -> registros_error
    # ------------------------------------------------------------------
    op.rename_table("error_logs", "registros_error")
    _rename_columns(
        "registros_error",
        [
            ("execution_id", "ejecucion_id"),
            ("type", "tipo"),
            ("identifier", "identificador"),
            ("message", "mensaje"),
            ("created_at", "creado_en"),
        ],
    )
    _rename_index(
        [
            ("ix_error_logs_id", "ix_registros_error_id"),
            ("ix_error_logs_execution_id", "ix_registros_error_ejecucion_id"),
        ]
    )
    _rename_constraint(
        "registros_error",
        [("error_logs_execution_id_fkey", "registros_error_ejecucion_id_fkey")],
    )

    # ------------------------------------------------------------------
    # execution_logs -> registros_ejecucion
    # ------------------------------------------------------------------
    op.rename_table("execution_logs", "registros_ejecucion")
    _rename_columns(
        "registros_ejecucion",
        [
            ("execution_id", "ejecucion_id"),
            ("phase", "fase"),
            ("action", "accion"),
            ("identifier", "identificador"),
            ("detail", "detalle"),
            ("created_at", "creado_en"),
        ],
    )
    _rename_index(
        [
            ("ix_execution_logs_id", "ix_registros_ejecucion_id"),
            ("ix_execution_logs_execution_id", "ix_registros_ejecucion_ejecucion_id"),
        ]
    )
    _rename_constraint(
        "registros_ejecucion",
        [("execution_logs_execution_id_fkey", "registros_ejecucion_ejecucion_id_fkey")],
    )

    # ------------------------------------------------------------------
    # operation_batches -> lotes_operacion
    # ------------------------------------------------------------------
    op.rename_table("operation_batches", "lotes_operacion")
    _rename_columns(
        "lotes_operacion",
        [
            ("batch_id", "id_lote"),
            ("entity_type", "tipo_entidad"),
            ("action", "accion"),
            ("completed", "completados"),
            ("failed", "fallidos"),
            ("created_at", "creado_en"),
            ("completed_at", "completado_en"),
        ],
    )
    _rename_index(
        [
            ("ix_operation_batches_id", "ix_lotes_operacion_id"),
            ("ix_operation_batches_batch_id", "ix_lotes_operacion_id_lote"),
            ("ix_operation_batches_created_at", "ix_lotes_operacion_creado_en"),
        ]
    )
    _rename_constraint(
        "lotes_operacion",
        [("operation_batches_batch_id_key", "lotes_operacion_id_lote_key")],
    )

    # ------------------------------------------------------------------
    # operation_items -> items_operacion
    # ------------------------------------------------------------------
    op.rename_table("operation_items", "items_operacion")
    _rename_columns(
        "items_operacion",
        [
            ("batch_id", "id_lote"),
            ("identifier", "identificador"),
            ("status", "estado"),
            ("attempt", "intento"),
            ("error_message", "mensaje_error"),
            ("detail", "detalle"),
            ("created_at", "creado_en"),
            ("updated_at", "actualizado_en"),
        ],
    )
    _rename_index(
        [
            ("ix_operation_items_id", "ix_items_operacion_id"),
            ("ix_operation_items_batch_id", "ix_items_operacion_id_lote"),
            ("ix_operation_items_status", "ix_items_operacion_estado"),
        ]
    )
    _rename_constraint(
        "items_operacion",
        [("operation_items_batch_id_fkey", "items_operacion_id_lote_fkey")],
    )

    # ------------------------------------------------------------------
    # query_results -> resultados_consulta
    # ------------------------------------------------------------------
    op.rename_table("query_results", "resultados_consulta")
    _rename_columns(
        "resultados_consulta",
        [
            ("task_id", "id_tarea"),
            ("entity", "entidad"),
            ("params", "parametros"),
            ("status", "estado"),
            ("result_json", "resultado_json"),
            ("error_message", "mensaje_error"),
            ("total_count", "conteo_total"),
            ("created_at", "creado_en"),
            ("completed_at", "completado_en"),
        ],
    )
    _rename_index(
        [
            ("ix_query_results_id", "ix_resultados_consulta_id"),
            ("ix_query_results_task_id", "ix_resultados_consulta_id_tarea"),
        ]
    )
    _rename_constraint(
        "resultados_consulta",
        [("query_results_task_id_key", "resultados_consulta_id_tarea_key")],
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # resultados_consulta -> query_results
    # ------------------------------------------------------------------
    _rename_constraint(
        "resultados_consulta",
        [("resultados_consulta_id_tarea_key", "query_results_task_id_key")],
    )
    _rename_index(
        [
            ("ix_resultados_consulta_id", "ix_query_results_id"),
            ("ix_resultados_consulta_id_tarea", "ix_query_results_task_id"),
        ]
    )
    _rename_columns(
        "resultados_consulta",
        [
            ("id_tarea", "task_id"),
            ("entidad", "entity"),
            ("parametros", "params"),
            ("estado", "status"),
            ("resultado_json", "result_json"),
            ("mensaje_error", "error_message"),
            ("conteo_total", "total_count"),
            ("creado_en", "created_at"),
            ("completado_en", "completed_at"),
        ],
    )
    op.rename_table("resultados_consulta", "query_results")

    # ------------------------------------------------------------------
    # items_operacion -> operation_items
    # ------------------------------------------------------------------
    _rename_constraint(
        "items_operacion",
        [("items_operacion_id_lote_fkey", "operation_items_batch_id_fkey")],
    )
    _rename_index(
        [
            ("ix_items_operacion_id", "ix_operation_items_id"),
            ("ix_items_operacion_id_lote", "ix_operation_items_batch_id"),
            ("ix_items_operacion_estado", "ix_operation_items_status"),
        ]
    )
    _rename_columns(
        "items_operacion",
        [
            ("id_lote", "batch_id"),
            ("identificador", "identifier"),
            ("estado", "status"),
            ("intento", "attempt"),
            ("mensaje_error", "error_message"),
            ("detalle", "detail"),
            ("creado_en", "created_at"),
            ("actualizado_en", "updated_at"),
        ],
    )
    op.rename_table("items_operacion", "operation_items")

    # ------------------------------------------------------------------
    # lotes_operacion -> operation_batches
    # ------------------------------------------------------------------
    _rename_constraint(
        "lotes_operacion",
        [("lotes_operacion_id_lote_key", "operation_batches_batch_id_key")],
    )
    _rename_index(
        [
            ("ix_lotes_operacion_id", "ix_operation_batches_id"),
            ("ix_lotes_operacion_id_lote", "ix_operation_batches_batch_id"),
            ("ix_lotes_operacion_creado_en", "ix_operation_batches_created_at"),
        ]
    )
    _rename_columns(
        "lotes_operacion",
        [
            ("id_lote", "batch_id"),
            ("tipo_entidad", "entity_type"),
            ("accion", "action"),
            ("completados", "completed"),
            ("fallidos", "failed"),
            ("creado_en", "created_at"),
            ("completado_en", "completed_at"),
        ],
    )
    op.rename_table("lotes_operacion", "operation_batches")

    # ------------------------------------------------------------------
    # registros_ejecucion -> execution_logs
    # ------------------------------------------------------------------
    _rename_constraint(
        "registros_ejecucion",
        [("registros_ejecucion_ejecucion_id_fkey", "execution_logs_execution_id_fkey")],
    )
    _rename_index(
        [
            ("ix_registros_ejecucion_id", "ix_execution_logs_id"),
            ("ix_registros_ejecucion_ejecucion_id", "ix_execution_logs_execution_id"),
        ]
    )
    _rename_columns(
        "registros_ejecucion",
        [
            ("ejecucion_id", "execution_id"),
            ("fase", "phase"),
            ("accion", "action"),
            ("identificador", "identifier"),
            ("detalle", "detail"),
            ("creado_en", "created_at"),
        ],
    )
    op.rename_table("registros_ejecucion", "execution_logs")

    # ------------------------------------------------------------------
    # registros_error -> error_logs
    # ------------------------------------------------------------------
    _rename_constraint(
        "registros_error",
        [("registros_error_ejecucion_id_fkey", "error_logs_execution_id_fkey")],
    )
    _rename_index(
        [
            ("ix_registros_error_id", "ix_error_logs_id"),
            ("ix_registros_error_ejecucion_id", "ix_error_logs_execution_id"),
        ]
    )
    _rename_columns(
        "registros_error",
        [
            ("ejecucion_id", "execution_id"),
            ("tipo", "type"),
            ("identificador", "identifier"),
            ("mensaje", "message"),
            ("creado_en", "created_at"),
        ],
    )
    op.rename_table("registros_error", "error_logs")

    # ------------------------------------------------------------------
    # ejecuciones -> executions
    # ------------------------------------------------------------------
    _rename_index(
        [
            ("ix_ejecuciones_id", "ix_executions_id"),
            ("ix_ejecuciones_creado_en", "ix_executions_created_at"),
            ("ix_ejecuciones_semestre", "ix_executions_semester"),
            ("ix_ejecuciones_estado", "ix_executions_status"),
            ("ix_ejecuciones_modalidad", "ix_executions_modalidad"),
            ("ix_ejecuciones_id_tarea_celery", "ix_executions_celery_task_id"),
        ]
    )
    _rename_columns(
        "ejecuciones",
        [
            ("nombre_archivo", "filename"),
            ("semestre", "semester"),
            ("modo", "mode"),
            ("estado", "status"),
            ("metricas", "metrics"),
            ("conteo_errores", "errors_count"),
            ("directorio_reporte", "report_dir"),
            ("iniciado_en", "started_at"),
            ("completado_en", "completed_at"),
            ("duracion_segundos", "duration_seconds"),
            ("fase_actual", "current_phase"),
            ("porcentaje_progreso", "progress_pct"),
            ("progreso_actualizado_en", "progress_updated_at"),
            ("paso_actual", "current_step"),
            ("version_moodle", "moodle_version"),
            ("checkpoint_fase", "phase_checkpoint"),
            ("id_tarea_celery", "celery_task_id"),
            ("creado_en", "created_at"),
        ],
    )
    op.rename_table("ejecuciones", "executions")
