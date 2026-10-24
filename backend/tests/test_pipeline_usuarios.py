"""Pruebas del núcleo puro de resolución de usuarios (pipeline/users.py)."""

from app.pipeline.usuarios import (
    buscar_candidatos_docente,
    elegir_usuario_mas_antiguo,
    elegir_usuario_mas_reciente,
    indexar_docentes,
    nombres_difieren,
    normalizar_nombre,
    resolver_usuarios,
)


def _user(
    username="doc1",
    email="doc1@ut.edu.co",
    personal="doc1@gmail.com",
    first="Docente",
    last="Uno",
    cedula="12345",
):
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
        assert normalizar_nombre("  MARÍA  José  ") == "maria jose"

    def test_same_name_not_different(self):
        assert nombres_difieren("María José Suárez", "MARIA JOSE SUAREZ") is False

    def test_different_name_is_different(self):
        assert nombres_difieren("María José Suárez", "Carlos Andrés López") is True

    def test_minor_token_overlap_not_different(self):
        assert nombres_difieren("Ana María Pérez", "Ana Pérez") is False

    def test_empty_names_not_different(self):
        assert nombres_difieren("", "") is False


class TestResolveUsers:
    def test_resolves_by_email(self):
        user = _user()
        username_map, events = resolver_usuarios(
            [user],
            {"doc1@ut.edu.co": {"username": "m_doc1"}},
            {},
            {},
            {},
        )
        assert username_map == {"doc1": "m_doc1"}
        assert any(t == "user_resolved" for t, _, _ in events)

    def test_ignores_personal_email_when_institutional_missing(self):
        user = _user(email="", personal="doc1@gmail.com")
        username_map, events = resolver_usuarios(
            [user],
            {},
            {"doc1@gmail.com": {"username": "m_doc1"}},
            {},
            {},
        )
        assert username_map == {}
        assert events == []

    def test_ignores_username_when_institutional_email_not_found(self):
        user = _user()
        username_map, events = resolver_usuarios(
            [user],
            {},
            {},
            {"doc1": {"username": "m_doc1"}},
            {},
        )
        assert username_map == {}
        assert events == []

    def test_ignores_cedula_when_institutional_email_not_found(self):
        user = _user()
        username_map, events = resolver_usuarios(
            [user],
            {},
            {},
            {},
            {"12345": {"username": "m_doc1"}},
        )
        assert username_map == {}
        assert events == []

    def test_unmatched_user_skipped(self):
        user = _user()
        username_map, events = resolver_usuarios([user], {}, {}, {}, {})
        assert username_map == {}
        assert events == []

    def test_non_institutional_domain_is_not_mapped(self):
        user = _user(email="doc1@gmail.com")
        username_map, events = resolver_usuarios(
            [user],
            {"doc1@gmail.com": {"username": "m_doc1"}},
            {},
            {},
            {},
        )
        assert username_map == {}
        assert events == []

    def test_resolves_real_moodle_username_different_from_email_prefix(self):
        user = _user(username="doc1", email="doc1@ut.edu.co")
        username_map, events = resolver_usuarios(
            [user],
            {"doc1@ut.edu.co": {"username": "docente_real_moodle"}},
        )
        assert username_map == {"doc1": "docente_real_moodle"}
        assert events[0][0] == "user_resolved"
        assert events[0][1] == "docente_real_moodle"

    def test_email_match_never_checks_names(self):
        # Un match por email no debe emitir conflicto aunque el nombre difiera.
        user = _user()
        username_map, events = resolver_usuarios(
            [user],
            {"doc1@ut.edu.co": {"username": "m_doc1", "firstname": "Carlos", "lastname": "Andres"}},
            {},
            {},
            {},
        )
        assert username_map == {"doc1": "m_doc1"}
        assert all(t != "user_identity_conflict" for t, _, _ in events)

    def test_precedence_institutional_over_username(self):
        user = _user()
        username_map, _ = resolver_usuarios(
            [user],
            {"doc1@ut.edu.co": {"username": "por_email"}},
            {},
            {"doc1": {"username": "por_username"}},
            {},
        )
        assert username_map == {"doc1": "por_email"}


class TestPickOldestUser:
    def test_picks_lowest_timecreated(self):
        users = [
            {"id": "2", "username": "nuevo", "timecreated": "200"},
            {"id": "1", "username": "viejo", "timecreated": "100"},
        ]
        assert elegir_usuario_mas_antiguo(users)["username"] == "viejo"

    def test_ties_break_by_lowest_id(self):
        users = [
            {"id": "3", "username": "c", "timecreated": "100"},
            {"id": "1", "username": "a", "timecreated": "100"},
            {"id": "2", "username": "b", "timecreated": "100"},
        ]
        assert elegir_usuario_mas_antiguo(users)["username"] == "a"

    def test_falls_back_to_lowest_id_without_timecreated(self):
        # core_user_get_users_by_field puede no exponer timecreated.
        users = [
            {"id": "5", "username": "nuevo"},
            {"id": "2", "username": "viejo"},
        ]
        assert elegir_usuario_mas_antiguo(users)["username"] == "viejo"

    def test_prefers_users_with_timecreated(self):
        users = [
            {"id": "1", "username": "sin_tc"},
            {"id": "2", "username": "con_tc", "timecreated": "50"},
        ]
        assert elegir_usuario_mas_antiguo(users)["username"] == "con_tc"

    def test_single_user(self):
        users = [{"id": "1", "username": "unico", "timecreated": "0"}]
        assert elegir_usuario_mas_antiguo(users)["username"] == "unico"

    def test_empty_list_returns_none(self):
        assert elegir_usuario_mas_antiguo([]) is None


class TestPickNewestUser:
    def test_picks_highest_timecreated(self):
        users = [
            {"id": "1", "username": "viejo", "timecreated": "100"},
            {"id": "2", "username": "nuevo", "timecreated": "200"},
        ]
        assert elegir_usuario_mas_reciente(users)["username"] == "nuevo"

    def test_ties_break_by_highest_id(self):
        users = [
            {"id": "1", "username": "a", "timecreated": "100"},
            {"id": "3", "username": "c", "timecreated": "100"},
            {"id": "2", "username": "b", "timecreated": "100"},
        ]
        assert elegir_usuario_mas_reciente(users)["username"] == "c"

    def test_falls_back_to_highest_id_without_timecreated(self):
        users = [
            {"id": "2", "username": "viejo"},
            {"id": "5", "username": "nuevo"},
        ]
        assert elegir_usuario_mas_reciente(users)["username"] == "nuevo"

    def test_empty_list_returns_none(self):
        assert elegir_usuario_mas_reciente([]) is None


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
        idx = indexar_docentes(users, self._enrolments())
        sn = "IDE_0001_sI_101_G-01"
        assert sorted(idx["by_course"]["usernames"][sn]) == ["doc1", "doc2"]
        assert sorted(idx["by_course"]["emails"][sn]) == [
            "a@ut.edu.co",
            "b@ut.edu.co",
            "p1@gmail.com",
        ]
        assert sorted(idx["by_course"]["idnumbers"][sn]) == ["1", "2"]

        bk = ("IDE", "0001", "I", "101", "01")
        assert sorted(idx["by_base_key"]["usernames"][bk]) == ["doc1", "doc2"]

    def test_skips_enrolment_of_unknown_user(self):
        users = [_user(username="doc1")]
        enrolments = [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
            {"username": "fantasma", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]
        idx = indexar_docentes(users, enrolments)
        sn = "IDE_0001_sI_101_G-01"
        assert idx["by_course"]["usernames"][sn] == ["doc1"]


class TestLookupTeacherCandidates:
    def _single_user(self):
        return [_user(username="doc1", email="a@ut.edu.co", personal="")]

    def test_uses_exact_course_then_base_key(self):
        enrolments = [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]
        idx = indexar_docentes(self._single_user(), enrolments)

        emails, usernames, idnumbers = buscar_candidatos_docente(
            "IDE_0001_sI_101_G-01",
            idx,
        )
        assert emails == ["a@ut.edu.co"]
        assert usernames == ["doc1"]
        assert idnumbers == ["12345"]

    def test_falls_back_to_base_key_for_homologous_course(self):
        enrolments = [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01"},
        ]
        idx = indexar_docentes(self._single_user(), enrolments)

        # Mismo base_key (grupo 01) pero con sufijo de profesor distinto.
        emails, usernames, _ = buscar_candidatos_docente(
            "IDE_0001_sI_101_G-01_99999",
            idx,
        )
        assert emails == ["a@ut.edu.co"]
        assert usernames == ["doc1"]

    def test_empty_when_no_candidates(self):
        idx = indexar_docentes([], [])
        emails, usernames, idnumbers = buscar_candidatos_docente(
            "IDE_0001_sI_101_G-99",
            idx,
        )
        assert (emails, usernames, idnumbers) == ([], [], [])
