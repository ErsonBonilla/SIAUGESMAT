"""limpiar indices unicos (drift entre migraciones y modelos)

La revisión base creó ``lotes_operacion.id_lote`` y ``resultados_consulta.id_tarea``
como *constraint* UNIQUE + índice regular, mientras que los modelos usan
``unique=True, index=True`` (índice único). Esta revisión unifica ambas a un
único índice UNIQUE para eliminar el drift que reporta ``alembic check`` y
dejar cualquier base recién migrada idéntica a la que ya está en producción.

Como una FK puede depender del constraint/índice único (``items_operacion`` →
``lotes_operacion``), se dropea y recrea la FK alrededor de la unificación.

Es defensiva (online y offline): sobre bases que ya tienen el índice único
solo hace una recreación idempotente.

Revision ID: a1b2c3d4e5f7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-13 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "a1b2c3d4e5f7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (indice, tabla, columna, constraint, [(tabla_fk, nombre_fk, columna_fk)])
PENDIENTES = [
    (
        "ix_lotes_operacion_id_lote",
        "lotes_operacion",
        "id_lote",
        "lotes_operacion_id_lote_key",
        [("items_operacion", "items_operacion_id_lote_fkey", "id_lote")],
    ),
    (
        "ix_resultados_consulta_id_tarea",
        "resultados_consulta",
        "id_tarea",
        "resultados_consulta_id_tarea_key",
        [],
    ),
]


def _existe_index(nombre: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"), {"n": nombre}
        ).scalar()
    )


def _existe_constraint(nombre: str, contype: str = "u") -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = :n AND contype = :t "
                "AND connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')"
            ),
            {"n": nombre, "t": contype},
        ).scalar()
    )


def _drop_index_if_exists(index: str) -> None:
    if context.is_offline_mode() or _existe_index(index):
        op.execute(f"DROP INDEX {index}")


def _drop_constraint_if_exists(table: str, constraint: str) -> None:
    if context.is_offline_mode() or _existe_constraint(constraint):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")


def _drop_fk_if_exists(table: str, fk: str) -> None:
    if context.is_offline_mode() or _existe_constraint(fk, contype="f"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {fk}")


def _create_unique_index_if_missing(index: str, table: str, column: str) -> None:
    if context.is_offline_mode() or not _existe_index(index):
        op.execute(f"CREATE UNIQUE INDEX {index} ON {table} ({column})")


def _create_fk_if_missing(
    table: str, fk: str, column: str, ref_table: str, ref_column: str
) -> None:
    if context.is_offline_mode() or not _existe_constraint(fk, contype="f"):
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {fk} "
            f"FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_column})"
        )


def upgrade() -> None:
    for index, table, column, constraint, fks in PENDIENTES:
        for fk_table, fk, _fk_column in fks:
            _drop_fk_if_exists(fk_table, fk)
        _drop_constraint_if_exists(table, constraint)
        _drop_index_if_exists(index)
        _create_unique_index_if_missing(index, table, column)
        for fk_table, fk, fk_column in fks:
            _create_fk_if_missing(fk_table, fk, fk_column, table, column)


def downgrade() -> None:
    # Vuelve a la forma de la revisión base: constraint UNIQUE + índice regular.
    for index, table, column, constraint, fks in reversed(PENDIENTES):
        for fk_table, fk, _fk_column in fks:
            _drop_fk_if_exists(fk_table, fk)
        _drop_index_if_exists(index)
        if context.is_offline_mode() or not _existe_constraint(constraint):
            op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} UNIQUE ({column})")
        if context.is_offline_mode() or not _existe_index(index):
            op.execute(f"CREATE INDEX {index} ON {table} ({column})")
        for fk_table, fk, fk_column in fks:
            _create_fk_if_missing(fk_table, fk, fk_column, table, column)
