"""
Guardia de pureza del paquete `app/pipeline`.

Verifica por AST que ningún módulo del núcleo funcional importe símbolos de
infraestructura (base de datos, settings, HTTP, repositorios, Celery, pandas,
ETL de archivos) ni los use por nombre. El objetivo es impedir regresiones
que vuelvan a mezclar I/O con las transformaciones puras.
"""
import ast
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parents[1] / "app" / "pipeline"

# Prefijos de módulos cuyo import está prohibido en el núcleo puro.
FORBIDDEN_IMPORT_PREFIXES = (
    "app.db",
    "app.repositories",
    "app.core",
    "app.integrations",
    "app.workers",
    "app.celery_app",
    "app.api",
    "app.schemas",
    "app.main",
    "app.services.etl",
    "app.services.moodle",
    "app.services.moodle_factory",
    "app.services.moodle_errors",
    "app.services.error_messages",
    "app.services.novedades_service",
    "app.services.metrics_service",
    "app.services.reports",
    "app.services.charts",
    "sqlalchemy",
    "httpx",
    "pandas",
    "openpyxl",
    "celery",
    "fastapi",
    "requests",
    "aiohttp",
)

# Nombres prohibidos como identificadores dentro de los módulos puros.
FORBIDDEN_NAMES = {
    "settings",
    "Session",
    "SessionLocal",
    "get_moodle_service",
    "save_log",
    "save_error",
    "ETLService",
}


def _module_import_paths(tree: ast.Module) -> list:
    paths = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            paths.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module:
                paths.append(node.module)
    return paths


def _forbidden_imports(paths: list) -> list:
    return [
        p for p in paths
        if any(p == prefix or p.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    ]


def _forbidden_names(tree: ast.Module) -> list:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            found.append(node.id)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"save_log", "save_error"}
        ):
            found.append(node.func.attr)
    return found


def _pipeline_modules():
    assert PIPELINE_DIR.is_dir(), f"No existe el paquete pipeline en {PIPELINE_DIR}"
    return sorted(
        p for p in PIPELINE_DIR.glob("**/*.py")
        if p.name != "__init__.py"
    )


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


_MODULES = _pipeline_modules()


@pytest.mark.parametrize(
    "path",
    [str(p) for p in _MODULES],
    ids=[p.relative_to(PIPELINE_DIR).as_posix() for p in _MODULES],
)
def test_pipeline_module_is_pure(path):
    tree = _tree(Path(path))
    forbidden_imports = _forbidden_imports(_module_import_paths(tree))
    forbidden_names = _forbidden_names(tree)
    violations = []
    if forbidden_imports:
        violations.append(f"imports prohibidos: {sorted(set(forbidden_imports))}")
    if forbidden_names:
        violations.append(f"nombres prohibidos: {sorted(set(forbidden_names))}")
    assert not violations, f"{Path(path).name}: " + "; ".join(violations)


def test_pipeline_has_modules():
    assert len(_pipeline_modules()) >= 6, "El paquete pipeline perdió módulos"
