"""Tests para la consulta de docentes inactivos (por semestre, días, meses o años)."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.pipeline.shortnames import parse_shortname
from app.workers.query_tasks import (
    DEFAULT_INACTIVE_DAYS,
    DEFAULT_INACTIVE_MONTHS,
    DEFAULT_INACTIVE_YEARS,
    _build_inactive_rows,
    _days_to_cutoff,
    _do_query,
    _filter_orphan_courses,
    _months_to_cutoff,
    _semester_to_cutoff,
    _years_to_cutoff,
)

DAY = 86400
NOW = int(time.time())

SIA_COURSE = "IBA_0854_sIV_2022481_G-1"


def _teacher(username, lastcourseaccess=0, firstname="Doc", lastname="Uno"):
    return {
        "username": username,
        "firstname": firstname,
        "lastname": lastname,
        "email": f"{username}@ut.edu.co",
        "lastcourseaccess": lastcourseaccess,
    }


def _course(shortname, cid=1):
    return {"id": str(cid), "shortname": shortname, "fullname": f"Curso {shortname}"}


class TestCutoffHelpers:
    def test_default_inactive_days(self):
        assert DEFAULT_INACTIVE_DAYS == 15

    def test_default_inactive_months(self):
        assert DEFAULT_INACTIVE_MONTHS == 1

    def test_default_inactive_years(self):
        assert DEFAULT_INACTIVE_YEARS == 1

    def test_days_to_cutoff(self):
        cutoff = _days_to_cutoff(15)
        assert abs(cutoff - (int(time.time()) - 15 * DAY)) <= 2

    def test_months_to_cutoff(self):
        cutoff = _months_to_cutoff(1)
        assert abs(cutoff - (int(time.time()) - 30 * DAY)) <= 2

    def test_years_to_cutoff(self):
        cutoff = _years_to_cutoff(1)
        assert abs(cutoff - (int(time.time()) - 365 * DAY)) <= 2

    def test_semester_to_cutoff(self):
        assert _semester_to_cutoff("2025A") == 1735689600
        assert _semester_to_cutoff("2025B") == 1751328000


class TestBuildInactiveRows:
    def test_filters_by_cutoff(self):
        now = int(time.time())
        cutoff = now - 15 * DAY
        course = _course(SIA_COURSE)
        teachers = [
            _teacher("viejo", lastcourseaccess=now - 20 * DAY),
            _teacher("reciente", lastcourseaccess=now - 5 * DAY),
            _teacher("nunca"),
            _teacher("justo", lastcourseaccess=cutoff),  # >= cutoff → fuera
        ]
        rows = _build_inactive_rows(teachers, course, cutoff)
        assert [r["username"] for r in rows] == ["viejo", "nunca"]
        viejo = rows[0]
        assert viejo["teacher_name"] == "Doc Uno"
        assert viejo["email"] == "viejo@ut.edu.co"
        assert viejo["last_access"] == now - 20 * DAY
        assert viejo["days_since_last_access"] == 20
        # "nunca" aparece con 0 días
        assert rows[1]["last_access"] == 0
        assert rows[1]["days_since_last_access"] == 0

    def test_extrae_programa_y_cat(self):
        now = int(time.time())
        cutoff = now - 15 * DAY
        parsed = parse_shortname(SIA_COURSE)
        rows = _build_inactive_rows(
            [_teacher("doc1", lastcourseaccess=now - 30 * DAY)],
            _course(SIA_COURSE),
            cutoff,
        )
        assert rows[0]["course_shortname"] == SIA_COURSE
        assert rows[0]["program"] == parsed["cod_prog"]
        assert rows[0]["cat_prefix"] == parsed["cat_prefix"]
        assert rows[0]["cat"] == parsed["cat_prefix"]  # no mapeado → usa prefijo


class TestDoQueryInactiveTeachers:
    def _moodle(self, courses: list, teachers_by_course: dict) -> AsyncMock:
        moodle = AsyncMock()
        moodle.get_courses.return_value = courses
        call = moodle.get_enrolled_teachers_with_access
        call.side_effect = lambda cid: teachers_by_course.get(int(cid), [])
        return moodle

    @pytest.mark.asyncio
    async def test_by_days(self):
        now = int(time.time())
        siau = _course(SIA_COURSE, cid=1)
        otro = _course("NO-SIAUGE-001", cid=2)
        moodle = self._moodle(
            [siau, otro],
            {
                1: [
                    _teacher("viejo", lastcourseaccess=now - 20 * DAY),
                    _teacher("nuevo", lastcourseaccess=now - 5 * DAY),
                    _teacher("nunca"),
                ],
                2: [_teacher("otro")],
            },
        )
        qr = SimpleNamespace(entity="inactive_teachers", params={"days": 15})
        rows = await _do_query(moodle, qr)
        assert [r["username"] for r in rows] == ["viejo", "nunca"]
        # el curso que no es SIAUGESMAT nunca se consulta
        assert moodle.get_enrolled_teachers_with_access.call_count == 1

    @pytest.mark.asyncio
    async def test_by_semester(self):
        cutoff = _semester_to_cutoff("2025A")
        moodle = self._moodle(
            [_course(SIA_COURSE, cid=1)],
            {
                1: [
                    _teacher("antes", lastcourseaccess=cutoff - 1),
                    _teacher("despues", lastcourseaccess=cutoff + 1),
                ],
            },
        )
        qr = SimpleNamespace(entity="inactive_teachers", params={"semester": "2025A"})
        rows = await _do_query(moodle, qr)
        assert [r["username"] for r in rows] == ["antes"]

    @pytest.mark.asyncio
    async def test_requires_exactly_one_cutoff(self):
        moodle = AsyncMock()
        for params in (
            {},
            {"days": 15, "months": 3},
            {"days": 15, "years": 2},
            {"months": 3, "years": 2},
            {"days": 15, "semester": "2025A"},
        ):
            qr = SimpleNamespace(entity="inactive_teachers", params=params)
            with pytest.raises(ValueError):
                await _do_query(moodle, qr)

    @pytest.mark.asyncio
    async def test_invalid_days(self):
        moodle = AsyncMock()
        for bad in (0, -1, "abc", 4000):
            qr = SimpleNamespace(entity="inactive_teachers", params={"days": bad})
            with pytest.raises(ValueError):
                await _do_query(moodle, qr)

    @pytest.mark.asyncio
    async def test_by_months(self):
        now = int(time.time())
        cutoff = _months_to_cutoff(4)
        moodle = self._moodle(
            [_course(SIA_COURSE, cid=1)],
            {
                1: [
                    _teacher("viejo", lastcourseaccess=cutoff - 1),
                    _teacher("reciente", lastcourseaccess=now - 5 * DAY),
                ],
            },
        )
        qr = SimpleNamespace(entity="inactive_teachers", params={"months": 4})
        rows = await _do_query(moodle, qr)
        assert [r["username"] for r in rows] == ["viejo"]

    @pytest.mark.asyncio
    async def test_by_years(self):
        now = int(time.time())
        cutoff = _years_to_cutoff(2)
        moodle = self._moodle(
            [_course(SIA_COURSE, cid=1)],
            {
                1: [
                    _teacher("anos_sin_acceso", lastcourseaccess=cutoff - 1),
                    _teacher("reciente", lastcourseaccess=now - 5 * DAY),
                ],
            },
        )
        qr = SimpleNamespace(entity="inactive_teachers", params={"years": 2})
        rows = await _do_query(moodle, qr)
        assert [r["username"] for r in rows] == ["anos_sin_acceso"]

    @pytest.mark.asyncio
    async def test_invalid_months(self):
        moodle = AsyncMock()
        for bad in (0, -1, "abc", 13):
            qr = SimpleNamespace(entity="inactive_teachers", params={"months": bad})
            with pytest.raises(ValueError):
                await _do_query(moodle, qr)

    @pytest.mark.asyncio
    async def test_invalid_years(self):
        moodle = AsyncMock()
        for bad in (0, -1, "abc"):
            qr = SimpleNamespace(entity="inactive_teachers", params={"years": bad})
            with pytest.raises(ValueError):
                await _do_query(moodle, qr)

    @pytest.mark.asyncio
    async def test_years_unbounded_max(self):
        moodle = self._moodle([], {})
        qr = SimpleNamespace(entity="inactive_teachers", params={"years": 999})
        rows = await _do_query(moodle, qr)
        assert rows == []


class TestFilterOrphanCourses:
    def _moodle(self, teachers_by_course: dict) -> AsyncMock:
        moodle = AsyncMock()
        call = moodle.get_enrolled_teachers_with_access
        call.side_effect = lambda cid: teachers_by_course.get(int(cid), [])
        return moodle

    @pytest.mark.asyncio
    async def test_filters_courses_without_teacher(self):
        con_docente = _course(SIA_COURSE, cid=1)
        sinon = _course("UTR_1020_sI_2025101_G-2", cid=2)
        otro_sin = _course("VET_9990_sII_2025301_G-3", cid=3)
        no_sia = _course("NO-SIAUGE-001", cid=4)
        moodle = self._moodle({1: [_teacher("doc")], 2: [], 3: []})
        result = await _filter_orphan_courses(
            moodle, [con_docente, sinon, otro_sin, no_sia],
        )
        # solo SIAUGESMAT sin docentes; "con_docente" tiene 1 => no; "no_sia" se excluye
        assert [c["id"] for c in result] == ["2", "3"]
        # no se consultan docentes del curso no-SIAUGESMAT
        assert moodle.get_enrolled_teachers_with_access.call_count == 3

    @pytest.mark.asyncio
    async def test_orphan_option_in_do_query(self):
        siau = _course(SIA_COURSE, cid=1)
        sinon = _course("UTR_1020_sI_2025101_G-2", cid=2)
        cin = _course("VET_9990_sII_2025301_G-3", cid=3)
        moodle = AsyncMock()
        moodle.get_courses.return_value = [siau, sinon, cin]
        call = moodle.get_enrolled_teachers_with_access
        call.side_effect = lambda cid: [_teacher("doc")] if int(cid) == 1 else []
        qr = SimpleNamespace(entity="courses", params={"orphan": "true"})
        rows = await _do_query(moodle, qr)
        assert [c["id"] for c in rows] == ["2", "3"]

    @pytest.mark.asyncio
    async def test_orphan_off_returns_all(self):
        ahora = _course(SIA_COURSE, cid=1)
        moodle = AsyncMock()
        moodle.get_courses.return_value = [ahora]
        qr = SimpleNamespace(entity="courses", params={})
        rows = await _do_query(moodle, qr)
        assert rows == [ahora]
        moodle.get_enrolled_teachers_with_access.assert_not_called()
