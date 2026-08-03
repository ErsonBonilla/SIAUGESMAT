from unittest.mock import patch

import pytest

from app.repositories.operation_repo import (
    delete_batch,
    delete_old_batches,
    get_batch,
    get_batch_items,
    get_batch_status,
    pause_batch,
    resume_batch,
)


@pytest.fixture
def mock_batch():
    from datetime import datetime, timezone

    class MockBatch:
        batch_id = "test-batch-1"
        entity_type = "course"
        action = "create"
        modalidad = "DISTANCIA"
        created_at = datetime.now(timezone.utc)
        completed_at = None
    return MockBatch()


class TestGetBatchStatus:
    def test_not_found(self, client, auth_headers):
        with patch("app.api.v1.endpoints.batch_control.get_batch", return_value=None):
            resp = client.get("/api/v1/operations/batch/nonexistent/status", headers=auth_headers)
            assert resp.status_code == 404

    def test_returns_status(self, client, auth_headers, mock_batch):
        with (
            patch("app.api.v1.endpoints.batch_control.get_batch", return_value=mock_batch),
            patch("app.api.v1.endpoints.batch_control.get_batch_status", return_value={
                "total": 10, "pending": 2, "processing": 0, "paused": 0,
                "completed": 8, "failed": 0, "cancelled": 0,
            }),
            patch("app.api.v1.endpoints.batch_control.get_batch_items", return_value=[]),
        ):
            resp = client.get("/api/v1/operations/batch/test-batch-1/status", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["batch_id"] == "test-batch-1"
            assert data["total"] == 10
            assert data["completed"] == 8


class TestPauseBatch:
    def test_not_found(self, client, auth_headers):
        with patch("app.api.v1.endpoints.batch_control.get_batch", return_value=None):
            resp = client.post("/api/v1/operations/batch/nonexistent/pause", headers=auth_headers)
            assert resp.status_code == 404

    def test_pause_success(self, client, auth_headers, mock_batch):
        with (
            patch("app.api.v1.endpoints.batch_control.get_batch", return_value=mock_batch),
            patch("app.api.v1.endpoints.batch_control.pause_batch", return_value=5),
        ):
            resp = client.post("/api/v1/operations/batch/test-batch-1/pause", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["paused"] == 5


class TestResumeBatch:
    def test_not_found(self, client, auth_headers):
        with patch("app.api.v1.endpoints.batch_control.get_batch", return_value=None):
            resp = client.post("/api/v1/operations/batch/nonexistent/resume", headers=auth_headers)
            assert resp.status_code == 404

    def test_resume_success(self, client, auth_headers, mock_batch):
        with (
            patch("app.api.v1.endpoints.batch_control.get_batch", return_value=mock_batch),
            patch("app.api.v1.endpoints.batch_control.resume_batch", return_value=5),
        ):
            resp = client.post("/api/v1/operations/batch/test-batch-1/resume", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["resumed"] == 5


class TestDeleteBatch:
    def test_not_found(self, client, auth_headers):
        with patch("app.api.v1.endpoints.batch_control.get_batch", return_value=None):
            resp = client.delete("/api/v1/operations/batch/nonexistent", headers=auth_headers)
            assert resp.status_code == 404

    def test_delete_success(self, client, auth_headers, mock_batch):
        with (
            patch("app.api.v1.endpoints.batch_control.get_batch", return_value=mock_batch),
            patch("app.api.v1.endpoints.batch_control.delete_batch", return_value=True),
        ):
            resp = client.delete("/api/v1/operations/batch/test-batch-1", headers=auth_headers)
            assert resp.status_code == 200

    def test_delete_internal_error(self, client, auth_headers, mock_batch):
        with (
            patch("app.api.v1.endpoints.batch_control.get_batch", return_value=mock_batch),
            patch("app.api.v1.endpoints.batch_control.delete_batch", return_value=False),
        ):
            resp = client.delete("/api/v1/operations/batch/test-batch-1", headers=auth_headers)
            assert resp.status_code == 500


class TestDownloadReports:
    def test_not_found(self, client, auth_headers):
        with patch("app.api.v1.endpoints.batch_control.get_batch", return_value=None):
            resp = client.get(
                "/api/v1/operations/batch/nonexistent/reports/download", headers=auth_headers
            )
            assert resp.status_code == 404

    def test_download_zip_reaches_zip_endpoint(self, client, auth_headers, mock_batch, tmp_path):
        """El endpoint /reports/download debe llegar al ZIP (no a /{report_name})
        y `settings` debe estar importado (NameError si no)."""
        zf = tmp_path / "batch.zip"
        zf.write_bytes(b"zip-data")
        with (
            patch("app.api.v1.endpoints.batch_control.get_batch", return_value=mock_batch),
            patch("app.api.v1.endpoints.batch_control.get_all_batch_items", return_value=[]),
            patch("app.api.v1.endpoints.batch_control.save_batch_reports"),
            patch(
                "app.api.v1.endpoints.batch_control.build_batch_report_zip",
                return_value=(str(zf), "batch.zip"),
            ),
            patch("app.api.v1.endpoints.batch_control.os.path.exists", return_value=False),
        ):
            resp = client.get(
                "/api/v1/operations/batch/test-batch-1/reports/download",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.content == b"zip-data"
