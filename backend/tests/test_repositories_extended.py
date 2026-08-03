"""
Pruebas unitarias para los repositorios de QueryResult, OperationBatch y OperationItem.

Verifica que las funciones CRUD de query_repo y operation_repo funcionan correctamente.
"""

import pytest
from datetime import datetime, timezone

from app.db.models import QueryResult, OperationBatch, OperationItem
from app.repositories.query_repo import (
    get_query,
    create_query,
    set_query_running,
    set_query_completed,
    set_query_failed,
    delete_old_queries,
)
from app.repositories.operation_repo import (
    get_batch,
    get_pending_items,
    create_batch,
    add_item,
    update_item,
    update_batch_counts,
    complete_batch,
    get_batch_status,
    get_batch_items,
    get_all_batch_items,
    delete_old_batches,
    list_batches,
)


class TestQueryRepo:
    def test_create_and_get_query(self, test_db):
        qr = create_query(test_db, "task-1", "courses", {}, "DISTANCIA")
        assert qr.task_id == "task-1"
        assert qr.status == "pending"

        found = get_query(test_db, "task-1")
        assert found is not None
        assert found.entity == "courses"

    def test_get_query_not_found(self, test_db):
        assert get_query(test_db, "nonexistent") is None

    def test_set_query_running(self, test_db):
        create_query(test_db, "task-2", "users", {}, "DISTANCIA")
        qr = set_query_running(test_db, "task-2")
        assert qr.status == "running"
        assert qr.error_message is None
        assert qr.result_json is None
        assert qr.completed_at is None

    def test_set_query_completed(self, test_db):
        create_query(test_db, "task-3", "courses", {}, "DISTANCIA")
        set_query_completed(test_db, "task-3", [{"id": 1}], 1)
        qr = get_query(test_db, "task-3")
        assert qr.status == "completed"
        assert qr.result_json == [{"id": 1}]
        assert qr.total_count == 1
        assert qr.completed_at is not None

    def test_set_query_failed(self, test_db):
        create_query(test_db, "task-4", "courses", {}, "DISTANCIA")
        set_query_failed(test_db, "task-4", "Error de prueba")
        qr = get_query(test_db, "task-4")
        assert qr.status == "failed"
        assert qr.error_message == "Error de prueba"

    def test_delete_old_queries(self, test_db):
        qr = QueryResult(
            task_id="old-1", entity="courses", params={}, status="completed",
            modalidad="DISTANCIA",
            created_at=datetime.now(timezone.utc).replace(year=2000),
        )
        test_db.add(qr)
        test_db.commit()
        deleted = delete_old_queries(test_db, days=30)
        assert deleted >= 1
        assert get_query(test_db, "old-1") is None


class TestOperationRepo:
    @pytest.fixture
    def batch(self, test_db):
        b = create_batch(test_db, "batch-1", "users", "create", 3, "DISTANCIA")
        return b

    def test_create_and_get_batch(self, test_db, batch):
        assert batch.batch_id == "batch-1"
        found = get_batch(test_db, "batch-1")
        assert found.entity_type == "users"

    def test_create_batch_no_items(self, test_db, batch):
        b = get_batch(test_db, "batch-1")
        assert b.total == 3

    def test_add_item(self, test_db, batch):
        add_item(test_db, "batch-1", "user1", detail={"firstname": "A"}, status="pending")
        add_item(test_db, "batch-1", "user2", detail={"firstname": "B"}, status="pending")
        test_db.commit()
        items = get_pending_items(test_db, "batch-1")
        assert len(items) == 2

    def test_update_item_status(self, test_db, batch):
        add_item(test_db, "batch-1", "user1")
        test_db.commit()
        items = get_pending_items(test_db, "batch-1")
        update_item(test_db, items[0].id, "completed")
        assert get_pending_items(test_db, "batch-1") == []

    def test_update_item_with_error(self, test_db, batch):
        add_item(test_db, "batch-1", "user1")
        test_db.commit()
        items = get_pending_items(test_db, "batch-1")
        update_item(test_db, items[0].id, "failed", "Error")
        updated = get_batch_items(test_db, "batch-1", 0, 10)
        assert updated[0].status == "failed"
        assert updated[0].error_message == "Error"
        assert updated[0].attempt == 1

    def test_update_batch_counts(self, test_db, batch):
        update_batch_counts(test_db, "batch-1", completed=2, failed=1)
        b = get_batch(test_db, "batch-1")
        assert b.completed == 2
        assert b.failed == 1

    def test_complete_batch(self, test_db, batch):
        complete_batch(test_db, "batch-1")
        b = get_batch(test_db, "batch-1")
        assert b.completed_at is not None

    def test_get_batch_status(self, test_db, batch):
        add_item(test_db, "batch-1", "user1")
        add_item(test_db, "batch-1", "user2")
        test_db.commit()
        items = get_pending_items(test_db, "batch-1")
        update_item(test_db, items[0].id, "completed")
        update_item(test_db, items[1].id, "failed", "err")

        status = get_batch_status(test_db, "batch-1")
        assert status["total"] == 2
        assert status["completed"] == 1
        assert status["failed"] == 1
        assert status["pending"] == 0
        assert status["cancelled"] == 0

    def test_get_batch_items_paginated(self, test_db, batch):
        add_item(test_db, "batch-1", "user1")
        add_item(test_db, "batch-1", "user2")
        add_item(test_db, "batch-1", "user3")
        test_db.commit()
        page = get_batch_items(test_db, "batch-1", 0, 2)
        assert len(page) == 2

    def test_get_all_batch_items(self, test_db, batch):
        add_item(test_db, "batch-1", "user1")
        test_db.commit()
        all_items = get_all_batch_items(test_db, "batch-1")
        assert len(all_items) == 1

    def test_list_batches(self, test_db, batch):
        total, items = list_batches(test_db)
        assert total >= 1

        total_f, items_f = list_batches(test_db, entity_type="users", action="create")
        assert total_f >= 1

    def test_list_batches_empty_filter(self, test_db, batch):
        total, _ = list_batches(test_db, entity_type="courses")
        assert total == 0

    def test_delete_old_batches(self, test_db, batch):
        batch.created_at = datetime.now(timezone.utc).replace(year=2000)
        test_db.commit()
        deleted = delete_old_batches(test_db, days=30)
        assert deleted >= 1
        assert get_batch(test_db, "batch-1") is None

    def test_get_batch_nonexistent(self, test_db):
        assert get_batch(test_db, "no-such-batch") is None
