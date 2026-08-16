"""
Alineación modelos ORM ↔ migración renombradora a español.

Verifica por AST que la migración `20260813_0001_renombrar_tablas_y_columnas_a_espanol`
renombra cada tabla y columna al nombre español que declaran los modelos
(`app.db.modelos`). Previene un renombrado del ORM sin actualizar la migración
(o viceversa), que dejaría la base desincronizada.
"""

import ast
import re
from pathlib import Path

from app.db.base import Base

MIGRACION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260813_0001_renombrar_tablas_y_columnas_a_espanol.py"
)


def _extraer_operaciones() -> tuple[dict[str, str], dict[str, list[tuple[str, str]]]]:
    """Devuelve (tabla_antigua->nueva, {tabla: [(col_antigua, col_nueva)]})."""
    tree = ast.parse(MIGRACION.read_text(encoding="utf-8"))
    upgrade = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    tablas: dict[str, str] = {}
    columnas: dict[str, list[tuple[str, str]]] = {}
    for node in ast.walk(upgrade):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == "rename_table":
                old = ast.literal_eval(node.args[0])
                new = ast.literal_eval(node.args[1])
                tablas[old] = new
            elif isinstance(fn, ast.Name) and fn.id == "_rename_columns":
                tabla = ast.literal_eval(node.args[0])
                pares = ast.literal_eval(node.args[1])
                columnas[tabla] = [(o, n) for o, n in pares]
    return tablas, columnas


def test_migracion_renombra_todas_las_tablas_a_nombres_de_modelos():
    tablas, _ = _extraer_operaciones()
    assert set(tablas) == {
        "executions",
        "error_logs",
        "execution_logs",
        "operation_batches",
        "operation_items",
        "query_results",
    }
    for _antigua, nueva in tablas.items():
        assert nueva in Base.metadata.tables, f"tabla {nueva} no existe en los modelos"


def test_migracion_renombra_columnas_alineadas_con_modelos():
    tablas, columnas = _extraer_operaciones()
    for _antigua, nueva in tablas.items():
        pares = columnas[nueva]
        tabla_orm = Base.metadata.tables[nueva]
        columnas_orm = set(tabla_orm.columns.keys())
        for col_antigua, col_nueva in pares:
            assert col_nueva in columnas_orm, (
                f"columna {nueva}.{col_nueva} no existe en los modelos"
            )
            assert col_antigua not in columnas_orm, (
                f"columna {nueva}.{col_antigua} es inglesa y debería haberse renombrado"
            )


def test_no_quedan_nombres_ingleses_en_el_orm():
    """Ninguna tabla/columna del ORM conserva un identificador inglés de la época pre-rename."""
    inglesas_tablas = {
        "executions",
        "error_logs",
        "execution_logs",
        "operation_batches",
        "operation_items",
        "query_results",
    }
    inglesas_columnas = {
        "filename",
        "semester",
        "mode",
        "status",
        "metrics",
        "errors_count",
        "report_dir",
        "started_at",
        "completed_at",
        "duration_seconds",
        "current_phase",
        "progress_pct",
        "progress_updated_at",
        "current_step",
        "moodle_version",
        "phase_checkpoint",
        "celery_task_id",
        "created_at",
        "execution_id",
        "identifier",
        "message",
        "phase",
        "action",
        "detail",
        "batch_id",
        "entity_type",
        "completed",
        "failed",
        "attempt",
        "error_message",
        "task_id",
        "entity",
        "params",
        "result_json",
        "total_count",
        "updated_at",
    }
    for nombre, tabla in Base.metadata.tables.items():
        assert nombre not in inglesas_tablas, f"tabla {nombre} es inglesa"
        for col in tabla.columns:
            assert col.name not in inglesas_columnas, f"columna {nombre}.{col.name} es inglesa"


def test_migracion_actualizada_es_defensiva():
    """Los helpers de renombre no asumen que índices/constraints existan."""
    txt = MIGRACION.read_text(encoding="utf-8")
    assert "WHERE indexname" in txt
    assert "WHERE conname" in txt
    assert re.search(r"pg_indexes", txt)
    assert re.search(r"pg_constraint", txt)


MIGRACION_LIMPIEZA = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260813_0002_limpiar_indices_unicos_a_espanol.py"
)


def _ast_de(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_migracion_limpieza_encadena_tras_renombradora():
    txt = MIGRACION_LIMPIEZA.read_text(encoding="utf-8")
    assert re.search(r"^revision: .* = \"a1b2c3d4e5f7\"", txt, re.MULTILINE)
    assert re.search(r"^down_revision: .* = \"a1b2c3d4e5f6\"", txt, re.MULTILINE)


def test_migracion_limpieza_unifica_drift_a_indice_unico():
    tree = _ast_de(MIGRACION_LIMPIEZA)
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "upgrade" for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "downgrade" for node in ast.walk(tree)
    )
    pendientes = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PENDIENTES" for t in node.targets)
    )
    assert len(pendientes) == 2
    assert {(i, t, c, k) for i, t, c, k, _fks in pendientes} == {
        ("ix_lotes_operacion_id_lote", "lotes_operacion", "id_lote", "lotes_operacion_id_lote_key"),
        (
            "ix_resultados_consulta_id_tarea",
            "resultados_consulta",
            "id_tarea",
            "resultados_consulta_id_tarea_key",
        ),
    }
    fks_lotes = pendientes[0][4]
    assert ("items_operacion", "items_operacion_id_lote_fkey", "id_lote") in fks_lotes
    txt = MIGRACION_LIMPIEZA.read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX {index} ON {table} ({column})" in txt
    assert "ALTER TABLE {table} DROP CONSTRAINT {constraint}" in txt
    assert "DROP INDEX {index}" in txt
    assert "FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_column})" in txt
