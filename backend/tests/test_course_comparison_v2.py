"""
Tests ampliados para CourseComparisonService.

Fusiona la cobertura de los antiguos test_course_comparison.py y
test_course_comparison_v2.py: parseo de shortnames, índice, edad y
visibilidad de cursos, los 6 casos de comparación y los 13 casos
ampliados (courses_with_teacher como dict, suffix migration,
hide_and_create, disappeared courses, cedula update, core matching).
"""

import time

import pytest

from app.pipeline.course_comparison import CourseComparisonService
from app.pipeline.course_comparison.index_builder import build_shortname_index
from app.pipeline.course_comparison.utils import get_course_age_seconds, is_course_hidden
from app.pipeline.shortnames import parse_shortname


def _make_moodle_course(
    shortname: str,
    visible: int = 1,
    timecreated: int = 0,
    customfields: list = None,
) -> dict:
    return {
        "shortname": shortname,
        "visible": visible,
        "timecreated": timecreated,
        "customfields": customfields or [],
    }


def _make_new_course(shortname: str) -> dict:
    return {"shortname": shortname}


def _mc(sn, visible=1, timecreated=0, customfields=None):
    return {
        "shortname": sn,
        "visible": visible,
        "timecreated": timecreated or int(time.time()) - 3600,
        "customfields": customfields or [],
    }


def _nc(sn):
    return {"shortname": sn}


class TestParseShortname:
    def test_valid_shortname(self):
        result = parse_shortname("IDE_0105_sI_202_G-01")
        assert result == {
            "cat_prefix": "IDE",
            "cod_prog": "0105",
            "cod_curso": "202",
            "semestre": "I",
            "grupo": "01",
            "suffix": None,
        }

    def test_valid_with_uraba(self):
        result = parse_shortname("URA_0305_sII_101_G-A")
        assert result["cat_prefix"] == "URA"
        assert result["grupo"] == "A"

    def test_invalid_format(self):
        assert parse_shortname("invalid") is None
        assert parse_shortname("") is None


class TestBuildIndex:
    def test_shortname_index(self):
        courses = [
            _make_moodle_course("IDE_0105_sI_202_G-01"),
            _make_moodle_course("IDE_0105_203_sI_G-01"),
        ]
        index = build_shortname_index(courses)
        assert "IDE_0105_sI_202_G-01" in index
        assert "IDE_0105_203_sI_G-01" in index
        assert len(index) == 2


class TestCourseAge:
    def test_age_from_timecreated(self):
        course = _make_moodle_course("TEST", timecreated=100000)
        age = get_course_age_seconds(course)
        assert age > 0


class TestIsCourseHidden:
    def test_hidden_course(self):
        course = _make_moodle_course("TEST", visible=0)
        assert is_course_hidden(course) is True

    def test_visible_course(self):
        course = _make_moodle_course("TEST", visible=1)
        assert is_course_hidden(course) is False


class TestComparison:
    """Pruebas de los 6 casos usando mock de MoodleService."""

    @pytest.mark.asyncio
    async def test_case_1_new_course(self):
        """Caso 1: Curso nuevo (shortname no existe en Moodle)."""
        existing_courses = []

        new_courses = [_make_new_course("IDE_0105_sI_202_G-01")]
        new_enrolments = [{"course_shortname": "IDE_0105_sI_202_G-01", "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses, new_courses, new_enrolments
        )

        assert len(result["to_create"]) == 1
        assert result["to_create"][0]["shortname"] == "IDE_0105_sI_202_G-01"
        assert len(result["to_delete"]) == 0
        assert len(result["to_activate"]) == 0

    @pytest.mark.asyncio
    async def test_case_2_same_professor(self):
        """Caso 2: Curso existe con el mismo profesor."""
        sn = "IDE_0105_sI_202_G-01"
        recent_time = int(__import__("time").time()) - 1000
        existing_courses = [
            _make_moodle_course(
                sn,
                visible=1,
                timecreated=recent_time,
                customfields=[
                    {"shortname": "professor", "value": "prof1"},
                ],
            ),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses,
            new_courses,
            new_enrolments,
            courses_with_teacher={sn: "prof1"},
        )

        assert len(result["to_create"]) == 0
        assert len(result["to_delete"]) == 0
        assert len(result["to_activate"]) == 0

    @pytest.mark.asyncio
    async def test_case_1b_same_professor_old_course(self):
        """Caso 1b: Mismo profesor pero curso ≥18 meses → recreate."""
        sn = "IDE_0105_sI_202_G-01"
        old_time = 100000  # más de 18 meses
        existing_courses = [
            _make_moodle_course(
                sn,
                timecreated=old_time,
                customfields=[
                    {"shortname": "professor", "value": "prof1"},
                ],
            ),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses,
            new_courses,
            new_enrolments,
            courses_with_teacher={sn: "prof1"},
        )

        assert any(d.get("shortname") == sn for d in result["to_delete"])
        assert any(c["shortname"] == sn for c in result["to_create"])
        assert result["to_delete"][0]["reason"] == "old_course_cleanup"
        assert result["to_create"][0]["reason"] == "old_course_cleanup"

    @pytest.mark.asyncio
    async def test_case_2_same_professor_hidden(self):
        """Caso 2 (excepción): Curso oculto con mismo profesor → activar."""
        sn = "IDE_0105_sI_202_G-01"
        recent_time = int(__import__("time").time()) - 1000
        existing_courses = [
            _make_moodle_course(
                sn,
                visible=0,
                timecreated=recent_time,
                customfields=[
                    {"shortname": "professor", "value": "prof1"},
                ],
            ),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses,
            new_courses,
            new_enrolments,
            courses_with_teacher={sn: "prof1"},
        )

        assert any(d.get("shortname") == sn for d in result["to_activate"])
        assert result["to_activate"][0]["reason"] == "same_professor_hidden"

    @pytest.mark.asyncio
    async def test_case_3_different_professor(self):
        """Caso 3: Curso existe con distinto profesor → hide_and_create."""
        sn = "IDE_0105_sI_202_G-01"
        recent_time = int(__import__("time").time()) - 1000
        existing_courses = [
            _make_moodle_course(
                sn,
                timecreated=recent_time,
                customfields=[
                    {"shortname": "professor", "value": "old_prof"},
                ],
            ),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "new_prof"}]

        result = await CourseComparisonService.compare(
            existing_courses,
            new_courses,
            new_enrolments,
            courses_with_teacher={sn: "old_prof"},
        )

        assert len(result["to_hide"]) >= 1
        assert result["to_hide"][0]["reason"] == "teacher_change_recent"
        assert any(c["shortname"] == sn for c in result["to_create"])
        assert any(c["reason"] == "teacher_change_recent" for c in result["to_create"])

    @pytest.mark.asyncio
    async def test_case_4_same_core_different_group_rename(self):
        """Caso 4: Mismo programa/curso, diferente grupo, mismo profesor.
        El grupo viejo ya no está en la nueva carga → renombrar el curso existente."""
        existing_sn = "IDE_0105_sI_202_G-01"
        new_sn = "IDE_0105_sI_202_G-02"

        existing_courses = [
            _make_moodle_course(
                existing_sn,
                customfields=[
                    {"shortname": "professor", "value": "prof1"},
                ],
            ),
        ]

        new_courses = [_make_new_course(new_sn)]
        new_enrolments = [{"course_shortname": new_sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses, new_courses, new_enrolments
        )

        updated = [u for u in result.get("to_update", []) if u["shortname"] == new_sn]
        assert len(updated) == 1
        assert updated[0]["old_shortname"] == existing_sn
        assert updated[0]["professor"] == "prof1"

    @pytest.mark.asyncio
    async def test_case_4b_same_core_multiple_groups_same_prof(self):
        """Caso 4b: Mismo programa/curso, el profesor da AMBOS grupos en la nueva carga.
        El grupo viejo SÍ está en la nueva carga → clonar."""
        existing_sn = "IDE_0105_sI_202_G-01"
        new_sn_1 = "IDE_0105_sI_202_G-01"
        new_sn_2 = "IDE_0105_sI_202_G-02"

        existing_courses = [
            _make_moodle_course(
                existing_sn,
                customfields=[
                    {"shortname": "professor", "value": "prof1"},
                ],
            ),
        ]

        new_courses = [_make_new_course(new_sn_1), _make_new_course(new_sn_2)]
        new_enrolments = [
            {"course_shortname": new_sn_1, "username": "prof1"},
            {"course_shortname": new_sn_2, "username": "prof1"},
        ]

        result = await CourseComparisonService.compare(
            existing_courses, new_courses, new_enrolments
        )

        created = [c for c in result["to_create"] if c["shortname"] == new_sn_2]
        assert len(created) == 1
        assert created[0].get("template_shortname") == existing_sn

    @pytest.mark.asyncio
    async def test_case_5_same_core_different_group_diff_prof(self):
        """Caso 5: Mismo programa/curso, diferente grupo, distinto profesor."""
        existing_sn = "IDE_0105_sI_202_G-01"
        new_sn = "IDE_0105_sI_202_G-02"

        existing_courses = [
            _make_moodle_course(
                existing_sn,
                customfields=[
                    {"shortname": "professor", "value": "prof1"},
                ],
            ),
        ]

        new_courses = [_make_new_course(new_sn)]
        new_enrolments = [{"course_shortname": new_sn, "username": "prof2"}]

        result = await CourseComparisonService.compare(
            existing_courses, new_courses, new_enrolments
        )

        created = [c for c in result["to_create"] if c["shortname"] == new_sn]
        assert len(created) == 1
        assert "template_shortname" not in created[0] or not created[0].get("template_shortname")

    @pytest.mark.asyncio
    async def test_case_6_disappeared_course(self):
        """Caso 6: Curso existente que ya no está en la nueva carga."""
        sn = "IDE_0105_sI_202_G-01"
        old_time = 100000
        existing_courses = [
            _make_moodle_course(sn, timecreated=old_time),
        ]

        # Excel vacío → no se elimina nada (sin programas en scope)
        result = await CourseComparisonService.compare(existing_courses, [], [])
        assert not any(d.get("shortname") == sn for d in result["to_delete"]), (
            "Excel vacío no debe eliminar cursos"
        )
        assert len(result["alerts"]) == 0

        # Excel con un curso de OTRO programa → el curso 0105 no se toca
        other_sn = "IDE_9999_sI_999_G-01"
        result2 = await CourseComparisonService.compare(
            existing_courses,
            [_make_new_course(other_sn)],
            [],
        )
        assert not any(d.get("shortname") == sn for d in result2["to_delete"]), (
            "Curso de otro programa no debe eliminarse"
        )

        # Excel con cursos del MISMO programa → si desapareció, se elimina
        same_prog_sn = "IDE_0105_sI_303_G-01"
        result3 = await CourseComparisonService.compare(
            existing_courses,
            [_make_new_course(same_prog_sn)],
            [{"course_shortname": same_prog_sn, "username": "prof1"}],
        )
        assert any(d.get("shortname") == sn for d in result3["to_delete"]), (
            "Curso desaparecido del mismo programa debe eliminarse"
        )
        assert result3["to_delete"][0]["reason"] == "disappeared"


class TestComplete:
    """13 test cases for CourseComparisonService."""

    @pytest.mark.asyncio
    async def test_1_new(self):
        r = await CourseComparisonService.compare(
            [],
            [_nc("IDE_0105_sI_202_G-01")],
            [{"course_shortname": "IDE_0105_sI_202_G-01", "username": "p1"}],
        )
        assert len(r["to_create"]) == 1

    @pytest.mark.asyncio
    async def test_2_same_prof(self):
        sn = "IDE_0105_sI_202_G-01"
        r = await CourseComparisonService.compare(
            [_mc(sn, customfields=[{"shortname": "professor", "value": "p1"}])],
            [_nc(sn)],
            [{"course_shortname": sn, "username": "p1"}],
            courses_with_teacher={sn: "p1"},
        )
        assert len(r["to_create"]) == 0

    @pytest.mark.asyncio
    async def test_3_diff_prof_dict(self):
        sn = "BAJ_0838_sI_1102188_G-1_123456"
        r = await CourseComparisonService.compare(
            [_mc(sn)],
            [_nc(sn)],
            [{"course_shortname": sn, "username": "new_prof"}],
            courses_with_teacher={sn: "old_prof"},
        )
        assert len(r["to_hide"]) >= 1 or any(d.get("shortname") == sn for d in r["to_delete"])
        assert len(r["to_create"]) >= 1

    @pytest.mark.asyncio
    async def test_4_orphan(self):
        sn = "IDE_0105_sI_202_G-01"
        r = await CourseComparisonService.compare(
            [_mc(sn)],
            [_nc(sn)],
            [{"course_shortname": sn, "username": "p1"}],
            courses_with_teacher={},
        )
        assert any(d.get("shortname") == sn for d in r["to_delete"])
        assert any(c["shortname"] == sn for c in r["to_create"])

    @pytest.mark.asyncio
    async def test_5_suffix_migration(self):
        old = "IBA_0854_sIV_2022481_G-1"
        new = "IBA_0854_sIV_2022481_G-1_14398493"
        r = await CourseComparisonService.compare(
            [_mc(old, customfields=[{"shortname": "professor", "value": "fandrade"}])],
            [_nc(new)],
            [{"course_shortname": new, "username": "fandrade"}],
            courses_with_teacher={old: "fandrade"},
        )
        u = [x for x in r["to_update"] if x["shortname"] == new]
        assert len(u) == 1 and u[0]["old_shortname"] == old

    @pytest.mark.asyncio
    async def test_6_suffix_diff_prof(self):
        old = "IBA_0854_sIV_2022481_G-1"
        new = "IBA_0854_sIV_2022481_G-1_14398493"
        r = await CourseComparisonService.compare(
            [_mc(old, customfields=[{"shortname": "professor", "value": "old_p"}])],
            [_nc(new)],
            [{"course_shortname": new, "username": "new_p"}],
            courses_with_teacher={old: "old_p"},
        )
        assert len(r["to_hide"]) >= 1 and len(r["to_create"]) >= 1

    @pytest.mark.asyncio
    async def test_6b_suffix_migration_resolved_username(self):
        # El username Moodle resuelto puede diferir del prefijo del correo
        # institucional (fandrade@ut.edu.co → fandrade_pes). Como la matrícula
        # ya usa el username real resuelto, el rename por agregar cédula sigue
        # disparándose al coincidir con el editingteacher del curso.
        old = "IBA_0854_sIV_2022481_G-1"
        new = "IBA_0854_sIV_2022481_G-1_14398493"
        r = await CourseComparisonService.compare(
            [_mc(old, customfields=[{"shortname": "professor", "value": "fandrade_pes"}])],
            [_nc(new)],
            [{"course_shortname": new, "username": "fandrade_pes"}],
            courses_with_teacher={old: "fandrade_pes"},
        )
        u = [x for x in r["to_update"] if x["shortname"] == new]
        assert len(u) == 1 and u[0]["old_shortname"] == old

    @pytest.mark.asyncio
    async def test_7_disappeared_old(self):
        sn = "IDE_0105_sI_202_G-01"
        r = await CourseComparisonService.compare(
            [_mc(sn, timecreated=100000)],
            [_nc("IDE_0105_sI_303_G-01")],
            [{"course_shortname": "IDE_0105_sI_303_G-01", "username": "p1"}],
        )
        assert any(d.get("shortname") == sn for d in r["to_delete"])

    @pytest.mark.asyncio
    async def test_8_disappeared_recent(self):
        sn = "IDE_0105_sI_202_G-01"
        r = await CourseComparisonService.compare(
            [_mc(sn, timecreated=int(time.time()) - 3600)],
            [_nc("IDE_0105_sI_303_G-01")],
            [{"course_shortname": "IDE_0105_sI_303_G-01", "username": "p1"}],
        )
        assert any(d.get("shortname") == sn for d in r["to_hide"])

    @pytest.mark.asyncio
    async def test_9_disappeared_hidden(self):
        sn = "IDE_0105_sI_202_G-01"
        r = await CourseComparisonService.compare(
            [_mc(sn, visible=0, timecreated=int(time.time()) - 3600)],
            [_nc("IDE_0105_sI_303_G-01")],
            [{"course_shortname": "IDE_0105_sI_303_G-01", "username": "p1"}],
        )
        assert not any(d.get("shortname") == sn for d in r["to_hide"])

    @pytest.mark.asyncio
    async def test_10_cedula_update(self):
        old = "TUN_0838_sI_1102188_G-1"
        new = "TUN_0838_sI_1102188_G-1_12345678"
        r = await CourseComparisonService.compare(
            [_mc(old, customfields=[{"shortname": "professor", "value": "p1"}])],
            [_nc(new)],
            [{"course_shortname": new, "username": "p1"}],
            courses_with_teacher={old: "p1"},
        )
        u = [x for x in r["to_update"] if x["shortname"] == new]
        assert len(u) == 1 and u[0]["old_shortname"] == old

    @pytest.mark.asyncio
    async def test_11_core_rename(self):
        old = "IDE_0105_sI_202_G-01"
        new = "IDE_0105_sI_202_G-02"
        r = await CourseComparisonService.compare(
            [_mc(old, customfields=[{"shortname": "professor", "value": "p1"}])],
            [_nc(new)],
            [{"course_shortname": new, "username": "p1"}],
        )
        u = [x for x in r["to_update"] if x["shortname"] == new]
        assert len(u) == 1 and u[0]["old_shortname"] == old

    @pytest.mark.asyncio
    async def test_12_core_create_with_template(self):
        old = "IDE_0105_sI_202_G-01"
        new2 = "IDE_0105_sI_202_G-02"
        r = await CourseComparisonService.compare(
            [_mc(old, customfields=[{"shortname": "professor", "value": "p1"}])],
            [_nc(old), _nc(new2)],
            [
                {"course_shortname": old, "username": "p1"},
                {"course_shortname": new2, "username": "p1"},
            ],
        )
        c = [x for x in r["to_create"] if x["shortname"] == new2]
        assert len(c) == 1 and c[0].get("template_shortname") == old

    @pytest.mark.asyncio
    async def test_13_core_diff_prof_create(self):
        new = "IDE_0105_sI_202_G-02"
        r = await CourseComparisonService.compare(
            [_mc("IDE_0105_sI_202_G-01", customfields=[{"shortname": "professor", "value": "p1"}])],
            [_nc(new)],
            [{"course_shortname": new, "username": "p2"}],
        )
        c = [x for x in r["to_create"] if x["shortname"] == new]
        assert len(c) == 1 and not c[0].get("template_shortname")
