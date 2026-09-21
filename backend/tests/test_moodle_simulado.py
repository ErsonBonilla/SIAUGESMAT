"""
Smoke offline del Moodle simulado (`backend/e2e/moodle_simulado.py`).

Levanta un ``ThreadingHTTPServer`` en un puerto efímero y ejercita las
wsfunctions clave (usuarios, cursos, matriculación) sin red externa ni Redis.
Pura stdlib, corre en CI.
"""

import importlib.util
import json
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def _cargar_mock():
    spec = importlib.util.spec_from_file_location(
        "moodle_simulado", RAIZ / "e2e" / "moodle_simulado.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


MOCK = _cargar_mock()


@pytest.fixture()
def servidor():
    server = ThreadingHTTPServer(("127.0.0.1", 0), MOCK.ManejadorMoodle)
    server.estado = MOCK.EstadoMoodle()
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    yield server
    server.shutdown()
    server.server_close()
    hilo.join(timeout=2)


def _ws(servidor, wsfunction, **parametros):
    query = urllib.parse.urlencode({"wsfunction": wsfunction, **parametros})
    url = f"http://127.0.0.1:{servidor.server_port}/webservice/rest/server.php?{query}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode())


def test_site_info_versiones(servidor):
    out = _ws(servidor, "core_webservice_get_site_info")
    assert out["release"] == "3.9"


def test_crear_usuarios_y_consultar_por_username(servidor):
    _ws(
        servidor,
        "core_user_create_users",
        **{
            "users[0][username]": "laparamom",
            "users[0][firstname]": "Luis",
            "users[0][email]": "laparamom@ut.edu.co",
        },
    )
    out = _ws(
        servidor,
        "core_user_get_users_by_field",
        field="username",
        **{"values[0]": "laparamom"},
    )
    assert [u["username"] for u in out] == ["laparamom"]
    assert out[0]["id"] > 0


def test_crear_cursos_y_consultar_por_shortname(servidor):
    creados = _ws(
        servidor,
        "core_course_create_courses",
        **{
            "courses[0][shortname]": "IBA_0992_sI_1201073",
            "courses[0][fullname]": "ELECTIVA I",
            "courses[0][categoryid]": "1",
        },
    )
    assert creados[0]["id"] > 0
    out = _ws(
        servidor,
        "core_course_get_courses_by_field",
        field="shortname",
        value="IBA_0992_sI_1201073",
    )
    assert out["courses"][0]["shortname"] == "IBA_0992_sI_1201073"


def test_matriculacion_y_consulta_de_matriculados(servidor):
    _ws(
        servidor,
        "core_user_create_users",
        **{"users[0][username]": "doc1", "users[0][email]": "doc1@ut.edu.co"},
    )
    users = _ws(servidor, "core_user_get_users_by_field", field="username", **{"values[0]": "doc1"})
    userid = users[0]["id"]

    _ws(
        servidor,
        "core_course_create_courses",
        **{"courses[0][shortname]": "C1", "courses[0][categoryid]": "0"},
    )
    curso = _ws(servidor, "core_course_get_courses_by_field", field="shortname", value="C1")[
        "courses"
    ][0]

    _ws(
        servidor,
        "enrol_manual_enrol_users",
        **{
            "enrolments[0][userid]": str(userid),
            "enrolments[0][courseid]": str(curso["id"]),
            "enrolments[0][roleid]": "5",
        },
    )
    out = _ws(servidor, "core_enrol_get_enrolled_users", courseid=str(curso["id"]))
    assert [u["username"] for u in out] == ["doc1"]


def test_wsfunction_desconocida_devuelve_lista_vacia(servidor):
    out = _ws(servidor, "core_algo_desconocido")
    assert out == []
