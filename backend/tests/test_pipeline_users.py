"""Pruebas del núcleo puro de resolución de usuarios (pipeline/users.py)."""

from app.pipeline.users import (
    index_teachers,
    lookup_teacher_candidates,
    names_differ,
    normalize_name,
    resolve_users,
)


def _user(username="doc1", email="doc1@ut.edu.co", personal="doc1@gmail.com",
          first="Docente", last="Uno", cedula="12345"):
    return {
        "username": username,
        "email": email,
        "email_personal": personal,
        "firstname": first,
        "lastname": last,
        "cedula": cedula,
    }


class TestNormalizeName:
    def test_normalize_removes_accents_and_case(self):
        assert normalize_name("  MARÍA  José  ") == "maria jose"

    def test_same_name_not_different(self):
        assert names_differ("María José Suárez", "MARIA JOSE SUAREZ") is False

    def test_different_name_is_different(self):
        assert names_differ("María José Suárez", "Carlos Andrés López") is True

    def test_minor_token_overlap_not_different(self):
        assert names_differ("Ana María Pérez", "Ana Pérez") is False

    def test_empty_names_not_different(self):
        assert names_differ("", "") is False


class TestResolveUsers:
    def test_resolves_by_email(self):
        user = _user()
        username_map, events = resolve_users(
            [user],
            {"doc1@ut.edu.co": {"username": "m_doc1"}},
            {}, {}, {},
        )
        assert username_map == {"doc1": "m_doc1"}
        assert any(t == "user_resolved" for t, _, _ in events)

    def test_resolves_by_personal_email(self):
        user = _user(email="", personal="doc1@gmail.com")
        username_map, _ = resolve_users(
            [user],
            {},
            {"doc1@gmail.com": {"username": "m_doc1"}},
            {}, {},
        )
        assert username_map == {"doc1": "m_doc1"}

    def test_resolves_by_username(self):
        user = _user()
        username_map, _ = resolve_users(
            [user],
            {}, {},
            {"doc1": {"username": "m_doc1"}},
            {},
        )
        assert username_map == {"doc1": "m_doc1"}

    def test_resolves_by_cedula(self):
        user = _user()
        username_map, _ = resolve_users(
            [user],
            {}, {}, {},
            {"12345": {"username": "m_doc1"}},
        )
        assert username_map == {"doc1": "m_doc1"}

    def test_unmatched_user_skipped(self):
        user = _user()
        username_map, events = resolve_users([user], {}, {}, {}, {})
        assert username_map == {}
        assert events == []

    def test_username_match_with_conflicting_name_is_not_mapped(self):
        user = _user()
        username_map, events = resolve_users(
            [user],
            {}, {},
            {"doc1": {"username": "m_doc1", "firstname": "Carlos", "lastname": "Andres"}},
            {},
        )
        assert username_map == {}
        assert events[0][0] == "user_identity_conflict"
        assert events[0][1] == "doc1"
        assert events[0][2]["matched_by"] == "username"

    def test_cedula_match_with_same_name_is_mapped(self):
        user = _user()
        username_map, _ = resolve_users(
            [user],
            {}, {}, {},
            {"12345": {"username": "m_doc1", "firstname": "Docente", "lastname": "Uno"}},
        )
        assert username_map == {"doc1": "m_doc1"}

    def test_email_match_never_checks_names(self):
        # Un match por email no debe emitir conflicto aunque el nombre difiera.
        user = _user()
        username_map, events = resolve_users(
            [user],
            {"doc1@ut.edu.co": {"username": "m_doc1", "firstname": "Carlos", "lastname": "Andres"}},
            {}, {}, {},
        )
        assert username_map == {"doc1": "m_doc1"}
        assert all(t != "user_identity_conflict" for t, _, _ in events)

    def test_precedence_institutional_over_username(self):
        user = _user()
        username_map, _ = resolve_users(
            [user],
            {"doc1@ut.edu.co": {"username": "por_email"}},
            {},
            {"doc1": {"username": "por_username"}},
            {},
        )
        assert username_map == {"doc1": "por_email"}


class TestIndexTeachers:
    def _enrolments(self):
        return [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
            {"username": "doc2", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]

    def test_indexes_by_course_and_base_key(self):
        users = [
            _user(username="doc1", email="a@ut.edu.co", personal="p1@gmail.com", cedula="1"),
            _user(username="doc2", email="b@ut.edu.co", personal="", cedula="2"),
        ]
        idx = index_teachers(users, self._enrolments())
        sn = "IDE_0001_sI_101_G-01"
        assert sorted(idx["by_course"]["usernames"][sn]) == ["doc1", "doc2"]
        assert sorted(idx["by_course"]["emails"][sn]) == ["a@ut.edu.co", "b@ut.edu.co", "p1@gmail.com"]
        assert sorted(idx["by_course"]["idnumbers"][sn]) == ["1", "2"]

        bk = ("IDE", "0001", "I", "101", "01")
        assert sorted(idx["by_base_key"]["usernames"][bk]) == ["doc1", "doc2"]

    def test_skips_enrolment_of_unknown_user(self):
        users = [_user(username="doc1")]
        enrolments = [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
            {"username": "fantasma", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]
        idx = index_teachers(users, enrolments)
        sn = "IDE_0001_sI_101_G-01"
        assert idx["by_course"]["usernames"][sn] == ["doc1"]


class TestLookupTeacherCandidates:
    def _single_user(self):
        return [_user(username="doc1", email="a@ut.edu.co", personal="")]

    def test_uses_exact_course_then_base_key(self):
        enrolments = [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]
        idx = index_teachers(self._single_user(), enrolments)

        emails, usernames, idnumbers = lookup_teacher_candidates(
            "IDE_0001_sI_101_G-01", idx,
        )
        assert emails == ["a@ut.edu.co"]
        assert usernames == ["doc1"]
        assert idnumbers == ["12345"]

    def test_falls_back_to_base_key_for_homologous_course(self):
        enrolments = [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]
        idx = index_teachers(self._single_user(), enrolments)

        # Mismo base_key (grupo 01) pero con sufijo de profesor distinto.
        emails, usernames, _ = lookup_teacher_candidates(
            "IDE_0001_sI_101_G-01_99999", idx,
        )
        assert emails == ["a@ut.edu.co"]
        assert usernames == ["doc1"]

    def test_empty_when_no_candidates(self):
        idx = index_teachers([], [])
        emails, usernames, idnumbers = lookup_teacher_candidates(
            "IDE_0001_sI_101_G-99", idx,
        )
        assert (emails, usernames, idnumbers) == ([], [], [])
