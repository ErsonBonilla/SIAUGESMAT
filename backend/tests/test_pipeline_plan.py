"""Pruebas del núcleo puro que deriva los logs del plan (pipeline/plan.py)."""

from app.pipeline.plan import ALERT_ACTION_BY_REASON, plan_log_entries


class TestPlanLogEntries:
    def test_plan_logs_are_prefixed(self):
        entries = plan_log_entries(
            {
                "logs": [
                    {"action": "course_created", "identifier": "C1", "detail": {"reason": "new"}},
                    {
                        "action": "course_deleted",
                        "identifier": "C2",
                        "detail": {"age_seconds": 864000},
                    },
                ],
                "alerts": [],
            }
        )
        assert entries == [
            ("planned_course_created", "C1", {"reason": "new"}),
            ("planned_course_deleted", "C2", {"age_seconds": 864000}),
        ]

    def test_alert_with_known_reason(self):
        entries = plan_log_entries(
            {
                "logs": [],
                "alerts": [
                    {"shortname": "C3", "reason": "disappeared_recent", "age_seconds": 7200},
                ],
            }
        )
        assert entries == [
            (
                "alert_disappeared_recent",
                "C3",
                {
                    "reason": "disappeared_recent",
                    "age_seconds": 7200,
                    "fullname": "",
                    "professor": "",
                },
            )
        ]

    def test_alert_teacher_change_sets_professor(self):
        entries = plan_log_entries(
            {
                "logs": [],
                "alerts": [
                    {
                        "shortname": "C4",
                        "reason": "teacher_change_recent",
                        "old_professor": "p1",
                        "new_professor": "p2",
                    },
                ],
            }
        )
        action, _sn, detail = entries[0]
        assert action == "alert_teacher_change_recent"
        assert detail["professor"] == "p2"
        assert detail["old_professor"] == "p1"
        assert detail["new_professor"] == "p2"
        assert detail["fullname"] == ""

    def test_alert_fullname_from_map(self):
        entries = plan_log_entries(
            {
                "logs": [],
                "alerts": [
                    {"shortname": "C1", "reason": "disappeared_recent", "age_seconds": 3600},
                ],
            },
            fullname_map={"C1": "Curso Uno"},
        )
        assert entries[0][2]["fullname"] == "Curso Uno"

    def test_unknown_reason_dropped(self):
        entries = plan_log_entries(
            {
                "logs": [],
                "alerts": [{"shortname": "C5", "reason": "reason_desconocido"}],
            }
        )
        assert entries == []

    def test_empty_comparison(self):
        assert plan_log_entries({}) == []


class TestAlertActionByReason:
    def test_mapping(self):
        assert ALERT_ACTION_BY_REASON == {
            "disappeared_recent": "alert_disappeared_recent",
            "teacher_change_recent": "alert_teacher_change_recent",
            "disappeared": "alert_disappeared",
            "orphan_course": "alert_orphan_course",
        }
