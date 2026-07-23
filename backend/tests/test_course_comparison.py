"""
Pruebas unitarias para CourseComparisonService (FASE 2).

Verifica los 6 casos de comparación entre la nueva carga académica
y los cursos existentes en Moodle.
"""

import pytest

from app.services.course_comparison import CourseComparisonService


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


class TestParseShortname:

    def test_valid_shortname(self):
        result = CourseComparisonService._parse_shortname("IDE_0105_sI_202_G-01")
        assert result == {
            "cat_prefix": "IDE",
            "cod_prog": "0105",
            "cod_curso": "202",
            "semestre": "I",
            "grupo": "01",
            "suffix": None,
        }

    def test_valid_with_uraba(self):
        result = CourseComparisonService._parse_shortname("URA_0305_sII_101_G-A")
        assert result["cat_prefix"] == "URA"
        assert result["grupo"] == "A"

    def test_invalid_format(self):
        assert CourseComparisonService._parse_shortname("invalid") is None
        assert CourseComparisonService._parse_shortname("") is None


class TestBuildIndex:

    def test_shortname_index(self):
        courses = [
            _make_moodle_course("IDE_0105_sI_202_G-01"),
            _make_moodle_course("IDE_0105_203_sI_G-01"),
        ]
        index = CourseComparisonService._build_shortname_index(courses)
        assert "IDE_0105_sI_202_G-01" in index
        assert "IDE_0105_203_sI_G-01" in index
        assert len(index) == 2


class TestCourseAge:

    def test_age_from_timecreated(self):
        course = _make_moodle_course("TEST", timecreated=100000)
        age = CourseComparisonService._get_course_age_seconds(course)
        assert age > 0


class TestIsCourseHidden:

    def test_hidden_course(self):
        course = _make_moodle_course("TEST", visible=0)
        assert CourseComparisonService._is_course_hidden(course) is True

    def test_visible_course(self):
        course = _make_moodle_course("TEST", visible=1)
        assert CourseComparisonService._is_course_hidden(course) is False


class TestComparison:
    """Pruebas de los 6 casos usando mock de MoodleService."""

    @pytest.mark.asyncio
    async def test_case_1_new_course(self):
        """Caso 1: Curso nuevo (shortname no existe en Moodle)."""
        existing_courses = []

        new_courses = [_make_new_course("IDE_0105_sI_202_G-01")]
        new_enrolments = [{"course_shortname": "IDE_0105_sI_202_G-01", "username": "prof1"}]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

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
            _make_moodle_course(sn, visible=1, timecreated=recent_time, customfields=[
                {"shortname": "professor", "value": "prof1"},
            ]),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses, new_courses, new_enrolments,
            courses_with_teacher={sn},
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
            _make_moodle_course(sn, timecreated=old_time, customfields=[
                {"shortname": "professor", "value": "prof1"},
            ]),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

        assert sn in result["to_delete"]
        assert any(c["shortname"] == sn for c in result["to_create"])

    @pytest.mark.asyncio
    async def test_case_2_same_professor_hidden(self):
        """Caso 2 (excepción): Curso oculto con mismo profesor → activar."""
        sn = "IDE_0105_sI_202_G-01"
        recent_time = int(__import__("time").time()) - 1000
        existing_courses = [
            _make_moodle_course(sn, visible=0, timecreated=recent_time, customfields=[
                {"shortname": "professor", "value": "prof1"},
            ]),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(
            existing_courses, new_courses, new_enrolments,
            courses_with_teacher={sn},
        )

        assert sn in result["to_activate"]

    @pytest.mark.asyncio
    async def test_case_3_different_professor(self):
        """Caso 3: Curso existe con distinto profesor (antiguo >6 meses)."""
        sn = "IDE_0105_sI_202_G-01"
        old_time = 100000  # más de 6 meses
        existing_courses = [
            _make_moodle_course(sn, timecreated=old_time, customfields=[
                {"shortname": "professor", "value": "old_prof"},
            ]),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "new_prof"}]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

        assert sn in result["to_delete"]
        assert any(c["shortname"] == sn for c in result["to_create"])

    @pytest.mark.asyncio
    async def test_case_3_different_professor_recent(self):
        """Caso 3 (excepción): Curso con distinto profesor pero <18 meses → recreate."""
        sn = "IDE_0105_sI_202_G-01"
        recent_time = int(__import__("time").time()) - 1000  # 1000 segundos atrás
        existing_courses = [
            _make_moodle_course(sn, timecreated=recent_time, customfields=[
                {"shortname": "professor", "value": "old_prof"},
            ]),
        ]

        new_courses = [_make_new_course(sn)]
        new_enrolments = [{"course_shortname": sn, "username": "new_prof"}]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

        assert sn in result["to_delete"]
        assert any(c["shortname"] == sn for c in result["to_create"])

    @pytest.mark.asyncio
    async def test_case_4_same_core_different_group_rename(self):
        """Caso 4: Mismo programa/curso, diferente grupo, mismo profesor.
        El grupo viejo ya no está en la nueva carga → renombrar el curso existente."""
        existing_sn = "IDE_0105_sI_202_G-01"
        new_sn = "IDE_0105_sI_202_G-02"

        existing_courses = [
            _make_moodle_course(existing_sn, customfields=[
                {"shortname": "professor", "value": "prof1"},
            ]),
        ]

        new_courses = [_make_new_course(new_sn)]
        new_enrolments = [{"course_shortname": new_sn, "username": "prof1"}]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

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
            _make_moodle_course(existing_sn, customfields=[
                {"shortname": "professor", "value": "prof1"},
            ]),
        ]

        new_courses = [_make_new_course(new_sn_1), _make_new_course(new_sn_2)]
        new_enrolments = [
            {"course_shortname": new_sn_1, "username": "prof1"},
            {"course_shortname": new_sn_2, "username": "prof1"},
        ]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

        created = [c for c in result["to_create"] if c["shortname"] == new_sn_2]
        assert len(created) == 1
        assert created[0].get("template_shortname") == existing_sn

    @pytest.mark.asyncio
    async def test_case_5_same_core_different_group_diff_prof(self):
        """Caso 5: Mismo programa/curso, diferente grupo, distinto profesor."""
        existing_sn = "IDE_0105_sI_202_G-01"
        new_sn = "IDE_0105_sI_202_G-02"

        existing_courses = [
            _make_moodle_course(existing_sn, customfields=[
                {"shortname": "professor", "value": "prof1"},
            ]),
        ]

        new_courses = [_make_new_course(new_sn)]
        new_enrolments = [{"course_shortname": new_sn, "username": "prof2"}]

        result = await CourseComparisonService.compare(existing_courses, new_courses, new_enrolments)

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

        result = await CourseComparisonService.compare(existing_courses, [], [])

        assert sn in result["to_delete"]
