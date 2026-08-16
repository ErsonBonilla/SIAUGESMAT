import csv
import io
import logging

from app.services.roles import resolver_rol
from app.services.utilidades_categorias import ordenar_categorias

logger = logging.getLogger(__name__)


def validar_y_parsear_csv(content: str, column: str, label_plural: str) -> list[str]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV está vacío o no tiene cabecera")

    fieldnames = [name.strip().lower() for name in reader.fieldnames]
    if column not in fieldnames:
        raise ValueError(f"Falta la columna requerida: '{column}'")

    actual = next((n for n in reader.fieldnames if n.strip().lower() == column), column)
    values = []
    for row_num, row in enumerate(reader, start=2):
        value = row.get(actual, "").strip()
        if not value:
            raise ValueError(f"Fila {row_num}: '{column}' vacío")
        values.append(value)

    if not values:
        raise ValueError(f"No se encontraron {label_plural} en el archivo CSV.")
    return values


def validar_csv_usuarios(content: str, default_role: str = None) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV está vacío o no tiene cabecera")

    required = {"username", "firstname", "lastname", "email"}
    fieldnames = [n.strip().lower() for n in reader.fieldnames]
    missing = required - set(fieldnames)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")

    has_role_column = "role1" in {n.strip().lower() for n in reader.fieldnames}
    if not default_role and not has_role_column:
        raise ValueError("Debe incluir la columna 'role1' o especificar un default_role")

    users = []
    for row_num, row in enumerate(reader, start=2):
        user = {}
        for col in required:
            actual = next((n for n in reader.fieldnames if n.strip().lower() == col), col)
            value = row.get(actual, "").strip()
            if not value:
                raise ValueError(f"Fila {row_num}: '{col}' vacío")
            user[col] = value

        user["role1"] = default_role
        if has_role_column:
            role_actual = next(
                (n for n in reader.fieldnames if n.strip().lower() == "role1"), "role1"
            )
            csv_role = (row.get(role_actual) or "").strip()
            if csv_role:
                try:
                    resolver_rol(csv_role)
                except (ValueError, KeyError):
                    raise ValueError(f"Fila {row_num}: rol inválido '{csv_role}'") from None
                user["role1"] = csv_role

        fpc_field = next(
            (n for n in reader.fieldnames if n.strip().lower() == "forcepasswordchange"), None
        )
        if fpc_field:
            fpc = (row.get(fpc_field) or "").strip()
            if fpc in ("1", "0"):
                user["forcepasswordchange"] = fpc

        users.append(user)

    if not users:
        raise ValueError("No se encontraron usuarios en el archivo CSV.")
    return users


def _obtener_campo(
    row: dict, fieldnames: list, column: str, required: bool = False, row_num: int = 0
) -> str:
    actual = next((n for n in fieldnames if n.strip().lower() == column), column)
    value = (row.get(actual) or "").strip()
    if required and not value:
        raise ValueError(f"Fila {row_num}: '{column}' vacío")
    return value


def validar_csv_categorias(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV está vacío o no tiene cabecera")

    fieldnames = [n.strip().lower() for n in reader.fieldnames]
    if "name" not in fieldnames:
        raise ValueError("Falta la columna requerida: 'name'")

    categories = []
    for row_num, row in enumerate(reader, start=2):
        name = _obtener_campo(row, reader.fieldnames, "name", required=True, row_num=row_num)
        cat = {"name": name}
        idnumber = _obtener_campo(row, reader.fieldnames, "idnumber")
        if idnumber:
            cat["idnumber"] = idnumber
        parent = _obtener_campo(row, reader.fieldnames, "parent")
        cat["parent"] = parent
        description = _obtener_campo(row, reader.fieldnames, "description")
        if description:
            cat["description"] = description
        visible = _obtener_campo(row, reader.fieldnames, "visible")
        if visible in ("0", "1"):
            cat["visible"] = int(visible)
        categories.append(cat)

    if not categories:
        raise ValueError("No se encontraron categorías en el archivo CSV.")
    return ordenar_categorias(categories)
