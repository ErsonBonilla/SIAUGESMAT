from app.celery_app import celery_app


class TestCeleryAppConfig:
    def test_app_name(self):
        assert celery_app.main == "siaugesmat"

    def test_imports(self):
        expected = [
            "app.workers.tasks",
            "app.workers.phases.item_task",
            "app.workers.phases.common",
            "app.workers.phases.orchestrator",
            "app.workers.cleanup_tasks",
            "app.workers.operations_tasks",
            "app.workers.query_tasks",
        ]
        imports = celery_app.conf.get("imports")
        for mod in expected:
            assert mod in imports

    def test_task_serializer(self):
        assert celery_app.conf.get("task_serializer") == "json"

    def test_accept_content(self):
        assert celery_app.conf.get("accept_content") == ["json"]

    def test_timezone(self):
        assert celery_app.conf.get("timezone") == "America/Bogota"

    def test_enable_utc(self):
        assert celery_app.conf.get("enable_utc") is True

    def test_task_acks_late(self):
        assert celery_app.conf.get("task_acks_late") is True

    def test_task_ignore_result(self):
        assert celery_app.conf.get("task_ignore_result") is True

    def test_beat_schedule_contains_cleanup(self):
        schedule = celery_app.conf.get("beat_schedule")
        assert "cleanup-pending-executions" in schedule
        assert "cleanup-stuck-executions" in schedule

    def test_broker_url_set(self):
        assert celery_app.conf.get("broker_url") is not None
