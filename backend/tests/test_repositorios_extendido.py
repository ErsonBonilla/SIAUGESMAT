"""
Pruebas unitarias para los repositorios de QueryResult, OperationBatch y OperationItem.

Verifica que las funciones CRUD de query_repo y operation_repo funcionan correctamente.
"""

from datetime import UTC, datetime

import pytest

from app.db.modelos import ResultadoConsulta
from app.repositories.repositorio_consultas import (
    crear_consulta,
    eliminar_consultas_antiguas,
    marcar_consulta_completada,
    marcar_consulta_en_ejecucion,
    marcar_consulta_fallida,
    obtener_consulta,
)
from app.repositories.repositorio_operaciones import (
    actualizar_conteos_lote,
    actualizar_item,
    agregar_item,
    completar_lote,
    crear_lote,
    eliminar_lotes_antiguos,
    listar_lotes,
    obtener_estado_lote,
    obtener_items_lote,
    obtener_items_pendientes,
    obtener_lote,
    obtener_todos_items_lote,
)


class TestQueryRepo:
    def test_create_and_get_query(self, test_db):
        qr = crear_consulta(test_db, "task-1", "courses", {}, "DISTANCIA")
        assert qr.id_tarea == "task-1"
        assert qr.estado == "pending"

        found = obtener_consulta(test_db, "task-1")
        assert found is not None
        assert found.entidad == "courses"

    def test_get_query_not_found(self, test_db):
        assert obtener_consulta(test_db, "nonexistent") is None

    def test_set_query_running(self, test_db):
        crear_consulta(test_db, "task-2", "users", {}, "DISTANCIA")
        qr = marcar_consulta_en_ejecucion(test_db, "task-2")
        assert qr.estado == "running"
        assert qr.mensaje_error is None
        assert qr.resultado_json is None
        assert qr.completado_en is None

    def test_set_query_completed(self, test_db):
        crear_consulta(test_db, "task-3", "courses", {}, "DISTANCIA")
        marcar_consulta_completada(test_db, "task-3", [{"id": 1}], 1)
        qr = obtener_consulta(test_db, "task-3")
        assert qr.estado == "completed"
        assert qr.resultado_json == [{"id": 1}]
        assert qr.conteo_total == 1
        assert qr.completado_en is not None

    def test_set_query_failed(self, test_db):
        crear_consulta(test_db, "task-4", "courses", {}, "DISTANCIA")
        marcar_consulta_fallida(test_db, "task-4", "Error de prueba")
        qr = obtener_consulta(test_db, "task-4")
        assert qr.estado == "failed"
        assert qr.mensaje_error == "Error de prueba"

    def test_delete_old_queries(self, test_db):
        qr = ResultadoConsulta(
            id_tarea="old-1",
            entidad="courses",
            parametros={},
            estado="completed",
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC).replace(year=2000),
        )
        test_db.add(qr)
        test_db.commit()
        deleted = eliminar_consultas_antiguas(test_db, days=30)
        assert deleted >= 1
        assert obtener_consulta(test_db, "old-1") is None


class TestOperationRepo:
    @pytest.fixture
    def batch(self, test_db):
        return crear_lote(test_db, "batch-1", "users", "create", 3, "DISTANCIA")

    def test_create_and_get_batch(self, test_db, batch):
        assert batch.id_lote == "batch-1"
        found = obtener_lote(test_db, "batch-1")
        assert found.tipo_entidad == "users"

    def test_create_batch_no_items(self, test_db, batch):
        b = obtener_lote(test_db, "batch-1")
        assert b.total == 3

    def test_add_item(self, test_db, batch):
        agregar_item(test_db, "batch-1", "user1", detalle={"firstname": "A"}, estado="pending")
        agregar_item(test_db, "batch-1", "user2", detalle={"firstname": "B"}, estado="pending")
        test_db.commit()
        items = obtener_items_pendientes(test_db, "batch-1")
        assert len(items) == 2

    def test_update_item_status(self, test_db, batch):
        agregar_item(test_db, "batch-1", "user1")
        test_db.commit()
        items = obtener_items_pendientes(test_db, "batch-1")
        actualizar_item(test_db, items[0].id, "completed")
        assert obtener_items_pendientes(test_db, "batch-1") == []

    def test_update_item_with_error(self, test_db, batch):
        agregar_item(test_db, "batch-1", "user1")
        test_db.commit()
        items = obtener_items_pendientes(test_db, "batch-1")
        actualizar_item(test_db, items[0].id, "failed", "Error")
        updated = obtener_items_lote(test_db, "batch-1", 0, 10)
        assert updated[0].estado == "failed"
        assert updated[0].mensaje_error == "Error"
        assert updated[0].intento == 1

    def test_update_batch_counts(self, test_db, batch):
        actualizar_conteos_lote(test_db, "batch-1", completados=2, fallidos=1)
        b = obtener_lote(test_db, "batch-1")
        assert b.completados == 2
        assert b.fallidos == 1

    def test_complete_batch(self, test_db, batch):
        completar_lote(test_db, "batch-1")
        b = obtener_lote(test_db, "batch-1")
        assert b.completado_en is not None

    def test_get_batch_status(self, test_db, batch):
        agregar_item(test_db, "batch-1", "user1")
        agregar_item(test_db, "batch-1", "user2")
        test_db.commit()
        items = obtener_items_pendientes(test_db, "batch-1")
        actualizar_item(test_db, items[0].id, "completed")
        actualizar_item(test_db, items[1].id, "failed", "err")

        status = obtener_estado_lote(test_db, "batch-1")
        assert status["total"] == 2
        assert status["completed"] == 1
        assert status["failed"] == 1
        assert status["pending"] == 0
        assert status["cancelled"] == 0

    def test_get_batch_items_paginated(self, test_db, batch):
        agregar_item(test_db, "batch-1", "user1")
        agregar_item(test_db, "batch-1", "user2")
        agregar_item(test_db, "batch-1", "user3")
        test_db.commit()
        page = obtener_items_lote(test_db, "batch-1", 0, 2)
        assert len(page) == 2

    def test_get_all_batch_items(self, test_db, batch):
        agregar_item(test_db, "batch-1", "user1")
        test_db.commit()
        all_items = obtener_todos_items_lote(test_db, "batch-1")
        assert len(all_items) == 1

    def test_list_batches(self, test_db, batch):
        total, _items = listar_lotes(test_db)
        assert total >= 1

        total_f, _items_f = listar_lotes(test_db, tipo_entidad="users", accion="create")
        assert total_f >= 1

    def test_list_batches_empty_filter(self, test_db, batch):
        total, _ = listar_lotes(test_db, tipo_entidad="courses")
        assert total == 0

    def test_delete_old_batches(self, test_db, batch):
        batch.creado_en = datetime.now(UTC).replace(year=2000)
        test_db.commit()
        deleted = eliminar_lotes_antiguos(test_db, days=30)
        assert deleted >= 1
        assert obtener_lote(test_db, "batch-1") is None

    def test_get_batch_nonexistent(self, test_db):
        assert obtener_lote(test_db, "no-such-batch") is None


class TestExecutionErrorsCount:
    def _execution(self, test_db, metricas=None):
        from app.db.modelos import Ejecucion

        ex = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            estado="running",
            modalidad="DISTANCIA",
            metricas=metricas,
        )
        test_db.add(ex)
        test_db.commit()
        return ex

    def test_sync_errors_count_from_metrics(self, test_db):
        from app.repositories.repositorio_ejecuciones import sincronizar_conteo_errores

        ex = self._execution(test_db, metricas={"total_errors": 3})
        sincronizar_conteo_errores(test_db, ex.id)
        test_db.refresh(ex)
        assert ex.conteo_errores == 3

    def test_sync_errors_count_zero_when_no_metrics(self, test_db):
        from app.repositories.repositorio_ejecuciones import sincronizar_conteo_errores

        ex = self._execution(test_db, metricas=None)
        sincronizar_conteo_errores(test_db, ex.id)
        test_db.refresh(ex)
        assert ex.conteo_errores == 0
