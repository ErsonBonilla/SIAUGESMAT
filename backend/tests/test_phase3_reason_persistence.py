"""Tests para la persistencia del motivo (reason) en items de FASE 3 y auditoría.

Cubre M5: el contexto/reason generado por CourseComparisonService debe
persistir en los items (detail) y propagarse al log de auditoría.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import OperationItem
from app.workers.phases.item_task import _log_success
from app.workers.phases.phase3_structure import _create_phase3_items


def _comparison():
    return {
        "to_delete": [
            {"shortname": "IDE_0105_sI_202_G-01", "reason": "disappeared", "age_seconds": 100},
        ],
        "to_activate": [
            {"shortname": "IDE_0105_sI_303_G-01", "reason": "same_professor_hidden"},
        ],
        "to_hide": [
            {"shortname": "IDE_0105_sI_404_G-01", "reason": "teacher_change_recent"},
        ],
        "to_update": [
            {
                "shortname": "IDE_0105_sI_303_G-01",
                "old_shortname": "IDE_0105_sI_202_G-01",
                "reason": "core_rename",
                "professor": "prof1",
                "reactivate": True,
                "age_seconds": 500,
            },
        ],
        "to_create": [
            {
                "shortname": "IDE_0105_sI_505_G-01",
                "professor": "prof1",
                "reason": "new",
                "old_shortname": "IDE_0105_sI_404_G-01",
                "age_seconds": 60,
            },
        ],
    }


def _ctx_data():
    return {
        "courses": [
            {
                "shortname": "IDE_0105_sI_303_G-01",
                "fullname": "Curso Renombrado",
                "category_idnumber": "IDE_0105_sI",
                "templatecourse": None,
            },
            {
                "shortname": "IDE_0105_sI_505_G-01",
                "fullname": "Curso Nuevo",
                "category_idnumber": "IDE_0105_sI",
                "templatecourse": None,
            },
        ]
    }


class TestCreatePhase3ItemsPersistReason:
    def test_items_persist_reason_and_context(self, test_db):
        comparison = _comparison()
        with patch("app.workers.phases.phase3_structure._acquire_advisory_lock",
                   return_value=True), \
             patch("app.workers.phases.phase3_structure.get_moodle_service") as mock_factory:
            mock_ms = MagicMock()
            mock_ms.get_courses = AsyncMock(return_value=[])
            mock_ms.close = AsyncMock(return_value=None)
            mock_factory.return_value = mock_ms

            _create_phase3_items(test_db, 999, _ctx_data(), comparison, "DISTANCIA")

        items = test_db.query(OperationItem).filter(
            OperationItem.batch_id.like(f"etl_3_%_{999}")
        ).all()
        by_action = {}
        for it in items:
            by_action.setdefault((it.detail["action"], it.identifier), it)

        create_item = by_action[("create", "IDE_0105_sI_505_G-01")]
        assert create_item.detail["reason"] == "new"
        assert create_item.detail["old_shortname"] == "IDE_0105_sI_404_G-01"
        assert create_item.detail["professor"] == "prof1"
        assert create_item.detail["age_seconds"] == 60
        assert create_item.detail["fullname"] == "Curso Nuevo"

        delete_item = by_action[("delete", "IDE_0105_sI_202_G-01")]
        assert delete_item.detail["reason"] == "disappeared"
        assert delete_item.detail["age_seconds"] == 100

        activate_item = by_action[("activate", "IDE_0105_sI_303_G-01")]
        assert activate_item.detail["reason"] == "same_professor_hidden"

        hide_item = by_action[("hide", "IDE_0105_sI_404_G-01")]
        assert hide_item.detail["reason"] == "teacher_change_recent"

        rename_item = by_action[("rename", "IDE_0105_sI_303_G-01")]
        assert rename_item.detail["reason"] == "core_rename"
        assert rename_item.detail["old_shortname"] == "IDE_0105_sI_202_G-01"
        assert rename_item.detail["reactivate"] is True
        assert rename_item.detail["fullname"] == "Curso Renombrado"

    def test_items_without_reason_default_empty(self, test_db):
        comparison = {
            "to_delete": [{"shortname": "SN_001"}],
            "to_activate": [],
            "to_hide": [],
            "to_update": [],
            "to_create": [],
        }
        with patch("app.workers.phases.phase3_structure._acquire_advisory_lock",
                   return_value=True):
            _create_phase3_items(test_db, 998, {"courses": []}, comparison, "DISTANCIA")

        items = test_db.query(OperationItem).filter(
            OperationItem.batch_id.like(f"etl_3_%_{998}")
        ).all()
        assert len(items) == 1
        assert "reason" not in items[0].detail
        assert items[0].detail.get("age_seconds") is None


class TestLogSuccessPropagatesReason:
    def test_course_actions_copy_reason_to_log_detail(self):
        for action in ("delete", "activate", "hide", "create"):
            with patch("app.workers.phases.item_task.save_log") as mock_save:
                _log_success(
                    MagicMock(), 1, action, "SN_001",
                    {"reason": "some_reason", "old_shortname": "OLD",
                     "professor": "p1", "template_shortname": "TPL",
                     "age_seconds": 42, "recreate": True,
                     "fullname": "Curso Uno", "category_idnumber": "CAT"},
                )
            assert mock_save.called
            args = mock_save.call_args[0]
            log_detail = args[5]
            assert log_detail["reason"] == "some_reason"
            assert log_detail["old_shortname"] == "OLD"
            assert log_detail["professor"] == "p1"
            assert log_detail["template_shortname"] == "TPL"
            assert log_detail["age_seconds"] == 42
            assert log_detail["fullname"] == "Curso Uno"
            assert log_detail["category_idnumber"] == "CAT"

    def test_rename_copies_old_shortname_and_new_fullname(self):
        with patch("app.workers.phases.item_task.save_log") as mock_save:
            _log_success(MagicMock(), 1, "rename", "SN_NEW",
                         {"old_shortname": "SN_OLD", "reason": "core_rename",
                          "fullname": "Curso Renombrado"})
        args = mock_save.call_args[0]
        assert args[5]["old_shortname"] == "SN_OLD"
        assert args[5]["new_fullname"] == "Curso Renombrado"
        assert "reason" not in args[5]

    def test_enrol_copies_fullname(self):
        with patch("app.workers.phases.item_task.save_log") as mock_save:
            _log_success(MagicMock(), 1, "enrol", "user1",
                         {"course_shortname": "CUR_101",
                          "fullname": "Curso de Prueba"})
        args = mock_save.call_args[0]
        assert args[5]["course"] == "CUR_101"
        assert args[5]["fullname"] == "Curso de Prueba"

    def test_skips_reason_for_user_created(self):
        with patch("app.workers.phases.item_task.save_log") as mock_save:
            _log_success(MagicMock(), 1, "create_user", "user1",
                         {"reason": "user_reason"})
        assert not mock_save.called

    def test_no_execution_id_no_log(self):
        with patch("app.workers.phases.item_task.save_log") as mock_save:
            _log_success(MagicMock(), None, "delete", "SN_001",
                         {"reason": "some_reason"})
        assert not mock_save.called
