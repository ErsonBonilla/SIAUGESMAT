"""Pruebas del núcleo puro de detección de novedades."""

from app.pipeline.novedades import detect_novedades

IDE = "IDE_0001_sI_101_G-01"


def _course(shortname=IDE, fullname="Curso"):
    return {"shortname": shortname, "fullname": fullname}


def _data(courses, users=None, enrolments=None):
    return {
        "courses": courses,
        "users": users or [],
        "enrolments": enrolments or [],
    }


def _suffix_shortname(suffix):
    return f"IDE_0001_sI_101_G-01_{suffix}"


class TestDetectNovedades:
    def test_no_changes_yields_empty(self):
        old = _data([_course()], [], [{"username": "u1", "course_shortname": IDE}])
        new = _data([_course()], [], [{"username": "u1", "course_shortname": IDE}])
        novedades, stats = detect_novedades(old, new)
        assert novedades == []
        assert stats["total_compared"] == 3  # common 1 + old 1 + new 1

    def test_professor_change(self):
        old_sn = _suffix_shortname("12345")
        new_sn = _suffix_shortname("67890")
        old = _data(
            [_course(shortname=old_sn)],
            [{"username": "u1", "firstname": "Ana", "lastname": "Perez", "cedula": "12345"}],
            [{"username": "u1", "course_shortname": old_sn}],
        )
        new = _data(
            [_course(shortname=new_sn)],
            [{"username": "u2", "firstname": "Carlos", "lastname": "Lopez", "cedula": "67890"}],
            [{"username": "u2", "course_shortname": new_sn}],
        )
        novedades, stats = detect_novedades(old, new)
        assert len(novedades) == 1
        nov = novedades[0]
        assert nov["action"] == "cambio_profesor"
        assert nov["old_shortname"] == old_sn
        assert nov["new_shortname"] == new_sn
        assert nov["old_prof_cedula"] == "12345"
        assert nov["new_prof_cedula"] == "67890"
        assert nov["old_prof_name"] == "Ana Perez"
        assert nov["new_prof_name"] == "Carlos Lopez"
        assert stats["total_compared"] == 3  # common 1 + old 1 + new 1

    def test_deleted_course(self):
        old = _data([_course()], [], [{"username": "u1", "course_shortname": IDE}])
        new = _data([])
        novedades, _ = detect_novedades(old, new)
        assert len(novedades) == 1
        assert novedades[0]["action"] == "curso_eliminado"
        assert novedades[0]["new_shortname"] == ""

    def test_new_course(self):
        old = _data([])
        new = _data([_course()], [], [{"username": "u1", "course_shortname": IDE}])
        novedades, _ = detect_novedades(old, new)
        assert len(novedades) == 1
        assert novedades[0]["action"] == "curso_nuevo"
        assert novedades[0]["old_shortname"] == ""

    def test_total_compared_counts_union(self):
        old = _data([_course()])
        new = _data([_course()], users=[], enrolments=[])
        _, stats = detect_novedades(old, new)
        assert stats["total_compared"] == 3  # common 1 + old 1 + new 1

    def test_same_suffix_no_change_even_if_usernames_differ(self):
        old = _data(
            [_course()],
            [{"username": "u1", "firstname": "Ana", "lastname": "Perez", "cedula": "12345"}],
            [{"username": "u1", "course_shortname": IDE}],
        )
        new = _data(
            [_course()],
            [{"username": "u2", "firstname": "Carlos", "lastname": "Lopez", "cedula": "12345"}],
            [{"username": "u2", "course_shortname": IDE}],
        )
        novedades, _ = detect_novedades(old, new)
        assert novedades == []
