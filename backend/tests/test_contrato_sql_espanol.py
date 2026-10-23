"""
No hay identificadores de tablas/columnas ingleses en SQL crudo.

El refactor renombró todas las tablas y columnas a español. Cualquier SQL
crudo (``text(...)``/``execute(...)``) debe usar los nombres nuevos. Este test
escanea por AST todos los strings de `app/**` que parecen SQL y prohíbe los
identificadores pre-rename. No marca claves JSON de datos ni contratos externos
(nombres de tareas Celery, URLs, variables Python).
"""

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

INGLESAS_TABLAS = {
    "executions",
    "error_logs",
    "execution_logs",
    "operation_batches",
    "operation_items",
    "query_results",
}

INGLESAS_COLUMNAS = {
    "filename",
    "semester",
    "mode",
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
    "batch_id",
    "entity_type",
    "error_message",
    "task_id",
    "result_json",
    "total_count",
    "updated_at",
}

# Palabras que delatan un string como SQL (sentencia con referencias a tabla/columna).
SQL_KEYWORDS = re.compile(
    r"\b(ALTER\s+TABLE|SELECT\s+\S+\s+FROM|UPDATE\s+\w+|INSERT\s+INTO|DELETE\s+FROM|"
    r"\bFROM\s+\w+|JOIN\s+\w+|ON\s+CONFLICT|WHERE\s+\w+\.)\b",
    re.IGNORECASE,
)

TOKEN = re.compile(r"[\w.]+")


def _strings_sql(tree: ast.AST):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and SQL_KEYWORDS.search(node.value)
        ):
            yield node.value


def _identificadores_ingleses(sql: str):
    body = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", " ", sql)
    tokens = {t.split(".")[-1] for t in TOKEN.findall(body)}
    return tokens & INGLESAS_TABLAS | tokens & INGLESAS_COLUMNAS


def test_sql_crudo_no_tiene_identificadores_ingleses():
    hallados: list[str] = []
    for py in sorted(APP.rglob("*.py")):
        if "alembic" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for sql in _strings_sql(tree):
            prohibidos = _identificadores_ingleses(sql)
            if prohibidos:
                hallados.append(f"{py}: {sorted(prohibidos)} -> {sql.strip()[:120]}")
    assert not hallados, "\n".join(hallados)
