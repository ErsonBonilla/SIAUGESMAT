"""Tests del núcleo puro de cuentas duplicadas por email.

Cubre app/pipeline/duplicate_emails.py (agrupación por email y detección de
pares ambiguos).
"""

from datetime import UTC, datetime

from app.pipeline.correos_duplicados import (
    agrupar_filas,
    es_ambiguo,
    parsear_fecha,
)


class TestParseFecha:
    def test_datetime_full(self):
        assert parsear_fecha("2026-08-05 22:17:59") == datetime(2026, 8, 5, 22, 17, 59, tzinfo=UTC)

    def test_datetime_without_time(self):
        assert parsear_fecha("2020-06-20") == datetime(2020, 6, 20, tzinfo=UTC)

    def test_invalid(self):
        assert parsear_fecha("n/a") is None

    def test_empty(self):
        assert parsear_fecha("") is None
        assert parsear_fecha(None) is None


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
        groups = agrupar_filas(self._rows())
        assert [g.email for g in groups] == ["a@ut.edu.co", "b@ut.edu.co"]
        assert groups[0].count == 2
        assert groups[1].count == 1

    def test_oldest_and_newest(self):
        groups = agrupar_filas(self._rows())
        g = groups[0]
        assert g.mas_antiguo().username == "dpenaloza"
        assert g.mas_reciente().username == "dapenalozam"

    def test_email_normalized_lowercase(self):
        rows = [{"username": "u1", "fecha_creacion": "2020-01-01", "email": "A@UT.EDU.CO"}]
        assert agrupar_filas(rows)[0].email == "a@ut.edu.co"

    def test_empty_rows_skipped(self):
        assert (
            agrupar_filas([{"username": "", "fecha_creacion": "x", "email": "a@ut.edu.co"}]) == []
        )


class TestIsAmbiguous:
    def _group(self, dates):
        rows = [
            {"username": f"u{i}", "fecha_creacion": d, "email": "e@ut.edu.co"}
            for i, d in enumerate(dates)
        ]
        return agrupar_filas(rows)[0]

    def test_same_date_ambiguous(self):
        assert es_ambiguo(self._group(["2021-04-14 20:38:18", "2021-04-14 20:38:18"]))

    def test_different_dates_not_ambiguous(self):
        assert not es_ambiguo(self._group(["2020-06-20 11:32:14", "2026-05-13 19:18:23"]))

    def test_single_account_ambiguous(self):
        assert es_ambiguo(self._group(["2020-06-20 11:32:14"]))

    def test_unparseable_ambiguous(self):
        assert es_ambiguo(self._group(["no", "2026-05-13 19:18:23"]))
