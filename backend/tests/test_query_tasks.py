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
    _build_duplicate_email_rows,
    _build_inactive_rows,
    _days_to_cutoff,
    _do_query,
    _filter_orphan_courses,
    _get_all_known_usernames,
    _group_users_by_email,
    _months_to_cutoff,
    _normalize_email,
    _parse_cutoff,
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


def _course_ts(shortname, cid, timemodified, categoryname="CAT Sede Ibagué"):
    return {
        "id": str(cid),
        "shortname": shortname,
        "fullname": f"Curso {shortname}",
        "categoryname": categoryname,
        "timecreated": timemodified - 100 * DAY,
        "timemodified": timemodified,
    }


class TestParseCutoff:
    def test_days(self):
        assert abs(_parse_cutoff({"days": 15}) - _days_to_cutoff(15)) <= 2

    def test_months(self):
        assert abs(_parse_cutoff({"months": 4}) - _months_to_cutoff(4)) <= 2

    def test_years(self):
        assert abs(_parse_cutoff({"years": 2}) - _years_to_cutoff(2)) <= 2

    def test_semester(self):
        assert _parse_cutoff({"semester": "2025A"}) == _semester_to_cutoff("2025A")

    def test_requires_exactly_one(self):
        for params in (
            {},
            {"days": 15, "months": 3},
            {"years": 2, "semester": "2025A"},
            {"semester": "2025A", "days": 15, "months": 1, "years": 1},
        ):
            with pytest.raises(ValueError):
                _parse_cutoff(params)

    def test_invalid_values(self):
        for params in (
            {"days": 0},
            {"days": 400},
            {"months": 0},
            {"months": 13},
            {"years": 0},
            {"days": "abc"},
        ):
            with pytest.raises(ValueError):
                _parse_cutoff(params)

    def test_semester_invalid_shape(self):
        for semester in ("2025", "2025C", "2025X", "abcde"):
            with pytest.raises(ValueError):
                _parse_cutoff({"semester": semester})


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
            moodle,
            [con_docente, sinon, otro_sin, no_sia],
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
        qr = SimpleNamespace(entity="courses", params={"status": "orphan"})
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


class TestDoQueryInactiveCourses:
    def _moodle(self, courses: list) -> AsyncMock:
        moodle = AsyncMock()
        moodle.get_courses.return_value = courses
        return moodle

    @pytest.mark.asyncio
    async def test_by_days_filters_modified_cutoff(self):
        now = int(time.time())
        # SIN_USO tiene last_modified hace 30 días (corte 15 → incluido)
        sin_uso = _course_ts(SIA_COURSE, 1, now - 30 * DAY)
        # EN_USO tiene modificación reciente (corte 15 → excluido)
        en_uso = _course_ts("KEN_0852_sV_5031222_G-2", 2, now - 5 * DAY)
        no_sia = _course("NO-SIAUGE-001", 3)
        moodle = self._moodle([sin_uso, en_uso, no_sia])
        qr = SimpleNamespace(entity="inactive_courses", params={"days": 15})
        rows = await _do_query(moodle, qr)
        # solo SIAUGESMAT sin modificación > corte → queda "sin_uso"
        assert [r["shortname"] for r in rows] == [SIA_COURSE]

    @pytest.mark.asyncio
    async def test_excludes_courses_without_timemodified(self):
        now = int(time.time())
        sin_uso = _course_ts(SIA_COURSE, 1, now - 60 * DAY)
        sin_fecha = _course(SIA_COURSE, 2)  # sin timemodified
        moodle = self._moodle([sin_uso, sin_fecha])
        qr = SimpleNamespace(entity="inactive_courses", params={"months": 1})
        rows = await _do_query(moodle, qr)
        assert [r["shortname"] for r in rows] == [SIA_COURSE]

    @pytest.mark.asyncio
    async def test_builds_course_info_fields(self):
        now = int(time.time())
        course = _course_ts(SIA_COURSE, 7, now - 90 * DAY, categoryname="Urabá")
        moodle = self._moodle([course])
        qr = SimpleNamespace(entity="inactive_courses", params={"months": 2})
        rows = await _do_query(moodle, qr)
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "7"
        assert row["shortname"] == SIA_COURSE
        assert row["categoryname"] == "Urabá"
        parsed = parse_shortname(SIA_COURSE)
        assert row["program"] == parsed["cod_prog"]
        assert row["cat_prefix"] == parsed["cat_prefix"]
        assert row["cat"] == parsed["cat_prefix"]  # no mapeado → prefijo
        assert abs(int(row["days_since_modified"]) - 90) <= 1

    @pytest.mark.asyncio
    async def test_exactly_one_cutoff(self):
        moodle = AsyncMock()
        for params in ({}, {"days": 15, "months": 2}, {"years": 1, "semester": "2025A"}):
            qr = SimpleNamespace(entity="inactive_courses", params=params)
            with pytest.raises(ValueError):
                await _do_query(moodle, qr)

    @pytest.mark.asyncio
    async def test_by_semester(self):
        antes = _course_ts(SIA_COURSE, 1, _semester_to_cutoff("2024B") - 1)
        despues = _course_ts("UTRS_1122_s3_2025101_G-1", 2, _semester_to_cutoff("2024B") + 1)
        moodle = self._moodle([antes, despues])
        qr = SimpleNamespace(entity="inactive_courses", params={"semester": "2024B"})
        rows = await _do_query(moodle, qr)
        assert [r["shortname"] for r in rows] == [SIA_COURSE]


class TestGroupUsersByEmail:
    def _user(self, uid, username, email):
        return {"id": uid, "username": username, "email": email}

    def test_groups_by_normalized_email(self):
        users = [
            self._user(1, "u1", " A@UT.EDU.CO "),
            self._user(2, "u2", "a@ut.edu.co"),
            self._user(3, "u3", "b@ut.edu.co"),
        ]
        grouped = _group_users_by_email(users)
        assert len(grouped["a@ut.edu.co"]) == 2
        assert len(grouped["b@ut.edu.co"]) == 1

    def test_ignores_empty_emails(self):
        users = [self._user(1, "u1", ""), self._user(2, "u2", None)]
        assert _group_users_by_email(users) == {}

    def test_normalize_email(self):
        assert _normalize_email("  A@UT.EDU.CO ") == "a@ut.edu.co"
        assert _normalize_email(None) == ""


class TestBuildDuplicateEmailRows:
    def _user(self, uid, username, email):
        return {"id": uid, "username": username, "email": email}

    def test_only_groups_with_more_than_one_user(self):
        by_email = {
            "dup@ut.edu.co": [
                self._user(1, "u1", "dup@ut.edu.co"),
                self._user(2, "u2", "dup@ut.edu.co"),
            ],
            "single@ut.edu.co": [self._user(3, "u3", "single@ut.edu.co")],
        }
        rows = _build_duplicate_email_rows(by_email)
        assert len(rows) == 2
        assert all(r["email"] == "dup@ut.edu.co" for r in rows)
        assert all(r["duplicate_count"] == 2 for r in rows)

    def test_deduplicates_by_user_id(self):
        by_email = {
            "dup@ut.edu.co": [
                self._user(1, "u1", "dup@ut.edu.co"),
                self._user(2, "u2", "dup@ut.edu.co"),
                self._user(1, "u1", "dup@ut.edu.co"),
            ]
        }
        rows = _build_duplicate_email_rows(by_email)
        assert len(rows) == 2
        assert {r["username"] for r in rows} == {"u1", "u2"}

    def test_sorted_by_email_then_user_id(self):
        by_email = {
            "b@ut.edu.co": [self._user(2, "u2", "b@ut.edu.co"), self._user(1, "u1", "b@ut.edu.co")],
            "a@ut.edu.co": [self._user(3, "u3", "a@ut.edu.co"), self._user(4, "u4", "a@ut.edu.co")],
        }
        rows = _build_duplicate_email_rows(by_email)
        assert [r["email"] for r in rows] == ["a@ut.edu.co"] * 2 + ["b@ut.edu.co"] * 2
        assert [r["username"] for r in rows[:2]] == ["u3", "u4"]


class TestDoQueryDuplicateEmails:
    def _moodle(self, courses, users_pool, enrolled_by_course):
        moodle = AsyncMock()
        moodle.get_courses.return_value = courses

        async def fake_get_users(field, values):
            values_set = {str(v).lower() for v in values}
            if field == "email":
                return [u for u in users_pool if _normalize_email(u.get("email", "")) in values_set]
            return [u for u in users_pool if u.get("username") in values]

        moodle.get_users.side_effect = fake_get_users
        moodle.get_all_enrolled_users.side_effect = lambda cid: enrolled_by_course.get(int(cid), [])
        return moodle

    def _user(self, uid, username, email):
        return {
            "id": uid,
            "username": username,
            "firstname": f"Nombre{uid}",
            "lastname": f"Apellido{uid}",
            "email": email,
        }

    @pytest.mark.asyncio
    async def test_combines_logs_and_enrolled_sources(self, monkeypatch):
        monkeypatch.setattr(
            _get_all_known_usernames.__module__ + "._get_all_known_usernames",
            lambda: ["u1"],
        )
        pool = [
            self._user(1, "u1", "dup@ut.edu.co"),
            self._user(2, "u2", "dup@ut.edu.co"),
            self._user(3, "u3", "single@ut.edu.co"),
        ]
        moodle = self._moodle(
            [_course(SIA_COURSE, cid=1), _course("NO-SIAUGE-001", cid=2)],
            pool,
            {1: [pool[1], pool[2]]},
        )
        qr = SimpleNamespace(entity="duplicate_emails", params={})
        rows = await _do_query(moodle, qr)
        assert [r["email"] for r in rows] == ["dup@ut.edu.co"] * 2
        assert {r["username"] for r in rows} == {"u1", "u2"}
        assert all(r["duplicate_count"] == 2 for r in rows)
        # u2 fue encontrado via cursos (no en logs) y re-verificado por email
        assert moodle.get_all_enrolled_users.call_count == 1
        assert moodle.get_users.call_args_list[0][0] == ("username", ["u1"])

    @pytest.mark.asyncio
    async def test_reports_email_present_only_in_moodle(self, monkeypatch):
        monkeypatch.setattr(
            _get_all_known_usernames.__module__ + "._get_all_known_usernames",
            lambda: ["u1"],
        )
        # u2 comparte el correo con u1 pero no está en logs ni matriculado:
        # la re-consulta por email (field=email) lo descubre
        pool = [
            self._user(1, "u1", "dup@ut.edu.co"),
            self._user(2, "u2", "dup@ut.edu.co"),
        ]
        moodle = self._moodle([_course(SIA_COURSE, cid=1)], pool, {1: [pool[0]]})
        qr = SimpleNamespace(entity="duplicate_emails", params={})
        rows = await _do_query(moodle, qr)
        assert {r["username"] for r in rows} == {"u1", "u2"}

    @pytest.mark.asyncio
    async def test_ignores_unique_emails(self, monkeypatch):
        monkeypatch.setattr(
            _get_all_known_usernames.__module__ + "._get_all_known_usernames",
            lambda: ["u3"],
        )
        pool = [self._user(3, "u3", "single@ut.edu.co")]
        moodle = self._moodle([], pool, {})
        qr = SimpleNamespace(entity="duplicate_emails", params={})
        rows = await _do_query(moodle, qr)
        assert rows == []
