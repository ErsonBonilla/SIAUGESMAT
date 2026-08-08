"""
Tests ampliados para CourseComparisonService.
Cubre: courses_with_teacher como dict, suffix migration, hide_and_create,
disappeared courses, cedula update, core matching.
"""

import time

import pytest

from app.services.course_comparison import CourseComparisonService


def _mc(sn, visible=1, timecreated=0, customfields=None):
    return {
        "shortname": sn,
        "visible": visible,
        "timecreated": timecreated or int(time.time()) - 3600,
        "customfields": customfields or [],
    }


def _nc(sn):
    return {"shortname": sn}


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
