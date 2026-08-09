"""Tests del núcleo puro de cuentas duplicadas por email.

Cubre app/pipeline/duplicate_emails.py (agrupación por email y detección de
pares ambiguos) y valida la forma del CSV real `Corregir username.csv`.
"""

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.pipeline.duplicate_emails import (
    group_rows,
    is_ambiguous,
    parse_fecha,
)

REPO_CSV = Path(__file__).resolve().parents[2] / "Corregir username.csv"


class TestParseFecha:
    def test_datetime_full(self):
        assert parse_fecha("2026-08-05 22:17:59") == datetime(2026, 8, 5, 22, 17, 59, tzinfo=UTC)

    def test_datetime_without_time(self):
        assert parse_fecha("2020-06-20") == datetime(2020, 6, 20, tzinfo=UTC)

    def test_invalid(self):
        assert parse_fecha("n/a") is None

    def test_empty(self):
        assert parse_fecha("") is None
        assert parse_fecha(None) is None


class TestGroupRows:
    def _rows(self):
        return [
            {
                "username": "dpenaloza",
                "fecha_creacion": "2020-06-20 11:32:14",
                "email": "a@ut.edu.co",
            },
            {
                "username": "dapenalozam",
                "fecha_creacion": "2026-05-13 19:18:23",
                "email": "a@ut.edu.co",
            },
            {"username": "solo", "fecha_creacion": "2021-01-01 00:00:00", "email": "b@ut.edu.co"},
            {"username": "", "fecha_creacion": "2021-01-01", "email": "c@ut.edu.co"},
        ]

    def test_groups_basic(self):
        groups = group_rows(self._rows())
        assert [g.email for g in groups] == ["a@ut.edu.co", "b@ut.edu.co"]
        assert groups[0].count == 2
        assert groups[1].count == 1

    def test_oldest_and_newest(self):
        groups = group_rows(self._rows())
        g = groups[0]
        assert g.oldest().username == "dpenaloza"
        assert g.newest().username == "dapenalozam"

    def test_email_normalized_lowercase(self):
        rows = [{"username": "u1", "fecha_creacion": "2020-01-01", "email": "A@UT.EDU.CO"}]
        assert group_rows(rows)[0].email == "a@ut.edu.co"

    def test_empty_rows_skipped(self):
        assert group_rows([{"username": "", "fecha_creacion": "x", "email": "a@ut.edu.co"}]) == []


class TestIsAmbiguous:
    def _group(self, dates):
        rows = [
            {"username": f"u{i}", "fecha_creacion": d, "email": "e@ut.edu.co"}
            for i, d in enumerate(dates)
        ]
        return group_rows(rows)[0]

    def test_same_date_ambiguous(self):
        assert is_ambiguous(self._group(["2021-04-14 20:38:18", "2021-04-14 20:38:18"]))

    def test_different_dates_not_ambiguous(self):
        assert not is_ambiguous(self._group(["2020-06-20 11:32:14", "2026-05-13 19:18:23"]))

    def test_single_account_ambiguous(self):
        assert is_ambiguous(self._group(["2020-06-20 11:32:14"]))

    def test_unparseable_ambiguous(self):
        assert is_ambiguous(self._group(["no", "2026-05-13 19:18:23"]))


class TestRealCsv:
    pytestmark = pytest.mark.skipif(
        not REPO_CSV.exists(),
        reason="Corregir username.csv no esta presente en el repo (gitignored)",
    )

    def _real_rows(self):
        with open(REPO_CSV, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def test_shape_of_duplicated_emails(self):
        rows = self._real_rows()
        groups = group_rows(rows)
        assert len(groups) == 47
        assert all(g.count == 2 for g in groups)

    def test_only_same_date_pairs_are_ambiguous(self):
        groups = group_rows(self._real_rows())
        ambiguous = [g for g in groups if is_ambiguous(g)]
        assert len(ambiguous) == 3
        assert all(g.count == 2 for g in ambiguous)
        assert all(g.oldest().date == g.newest().date for g in ambiguous)
