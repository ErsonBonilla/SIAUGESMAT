#!/usr/bin/env python3
"""
Moodle simulado (HTTP mock) para probar el pipeline ETL sin tocar la
instancia real de Moodle.

Solo usa la stdlib. Implementa los web services que consume SIAUGESMAT en
`backend/app/services/operaciones_moodle.py` (modo `users` y, en parte,
`courses`), con estado en memoria determinista.

Uso:
    python e2e/moodle_simulado.py --port 8800

Luego apunta el backend/worker a http://localhost:8800 vía
`MOODLE_URL__DISTANCIA` / `MOODLE_URL__PRESENCIAL`. Ver `e2e/README.md`.

Cada request se registra en stdout (método, wsfunction y un resumen), de modo
que se puede verificar qué creó/actualizó el pipeline.
"""

import argparse
import json
import logging
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

logger = logging.getLogger(__name__)

UNKNOWN_WS_RESULT = []


class EstadoMoodle:
    """Estado en memoria del Moodle simulado (compartido entre requests)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.categorias: list[dict] = []
        self.cursos: list[dict] = []
        self.usuarios: list[dict] = []
        self.matriculas: list[dict] = []
        self._siguiente_id = 1

    def _nuevo_id(self) -> int:
        nid = self._siguiente_id
        self._siguiente_id += 1
        return nid

    def categorias_por_idnumber(self) -> dict[str, dict]:
        return {c.get("idnumber", ""): c for c in self.categorias if c.get("idnumber")}

    def usuarios_por(self, campo: str) -> dict[str, dict]:
        return {u.get(campo, ""): u for u in self.usuarios if u.get(campo)}

    def cursos_por_shortname(self) -> dict[str, dict]:
        return {c.get("shortname", ""): c for c in self.cursos if c.get("shortname")}


def _parametros_desindexados(params: dict[str, list[str]], prefijo: str) -> list[dict]:
    """Agrupa parámetros estilo `prefijo[i][clave]` en una lista de dicts ordenada."""
    grupos: dict[int, dict[str, str]] = {}
    pat = re.compile(rf"^{re.escape(prefijo)}\[(\d+)\]\[([^\]]+)\]$")
    for clave, valores in params.items():
        m = pat.match(clave)
        if not m or not valores:
            continue
        idx = int(m.group(1))
        grupos.setdefault(idx, {})[m.group(2)] = valores[0]
    return [grupos[i] for i in sorted(grupos)]


class ManejadorMoodle(BaseHTTPRequestHandler):
    """Manejador HTTP que despacha cada request a su wsfunction."""

    server_version = "MoodleSimulado/1.0"

    @property
    def estado(self) -> EstadoMoodle:
        return self.server.estado  # type: ignore[attr-defined]

    def _leer_parametros(self) -> dict[str, list[str]]:
        if self.command == "POST":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", "replace")
            return urllib.parse.parse_qs(body, keep_blank_values=True)
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    def _responder(self, data) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, mensaje: str, codigo: str = "error") -> None:
        self._responder({"error": mensaje, "errorcode": codigo, "exception": mensaje})

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def _dispatch(self) -> None:
        params = self._leer_parametros()
        wsfunction = (params.get("wsfunction") or [""])[0]
        log_resumen = self._resumen(params, wsfunction)
        logger.info("%s %s %s", self.command, wsfunction, log_resumen)
        try:
            resultado = self._ejecutar(wsfunction, params)
            self._responder(resultado)
        except KeyError as e:
            self._error(f"Falta parametro: {e}", "invalidparameter")
        except Exception as e:
            self._error(str(e)[:300], "moodle_simulado_error")

    # ------------------------------------------------------------------
    # Resumen de cada request (para logs legibles)
    # ------------------------------------------------------------------

    PREFIJO_POR_WS: ClassVar[dict[str, str]] = {
        "core_user_create_users": "users",
        "core_course_create_courses": "courses",
        "core_course_create_categories": "categories",
    }

    def _resumen(self, params: dict[str, list[str]], wsfunction: str) -> str:
        try:
            if wsfunction in self.PREFIJO_POR_WS:
                items = _parametros_desindexados(params, self.PREFIJO_POR_WS[wsfunction])
            elif wsfunction == "core_user_get_users_by_field":
                values = [v[0] for k, v in params.items() if k.startswith("values[")]
                return f"field={params.get('field', [''])[0]} n={len(values)}"
            else:
                items = []
            if items:
                nombres = [
                    str(i.get("username") or i.get("shortname") or i.get("name"))
                    for i in items
                    if i
                ]
                return f"n={len(nombres)} -> {', '.join(nombres[:8])}"
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Dispatch de wsfunctions
    # ------------------------------------------------------------------

    def _ejecutar(self, wsfunction: str, params: dict[str, list[str]]):
        with self.estado.lock:
            if wsfunction == "core_webservice_get_site_info":
                return {
                    "sitename": "Moodle simulado SIAUGESMAT",
                    "version": "2020061500",
                    "release": "3.9",
                    "username": "admin",
                    "userid": 2,
                    "firstname": "Admin",
                    "lastname": "Simulado",
                }
            if wsfunction == "core_course_get_categories":
                return self.estado.categorias
            if wsfunction == "core_course_create_categories":
                return self._crear_categorias(params)
            if wsfunction == "core_course_update_categories":
                return self._actualizar_categorias(params)
            if wsfunction == "core_course_delete_categories":
                return self._eliminar_categorias(params)
            if wsfunction == "core_course_get_courses":
                return self.estado.cursos
            if wsfunction == "core_course_get_courses_by_field":
                campo = params.get("field", [""])[0]
                valor = params.get("value", [""])[0]
                if campo == "shortname":
                    curso = self.estado.cursos_por_shortname().get(valor)
                    return {"courses": [curso] if curso else []}
                return {"courses": []}
            if wsfunction == "core_course_create_courses":
                return self._crear_cursos(params)
            if wsfunction == "core_course_update_courses":
                return self._actualizar_cursos(params)
            if wsfunction == "core_course_delete_courses":
                return self._eliminar_cursos(params)
            if wsfunction == "core_course_duplicate_course":
                return {"id": self.estado._nuevo_id()}
            if wsfunction == "core_course_import_course":
                return []
            if wsfunction == "core_enrol_get_course_enrolment_methods":
                courseid = params.get("courseid", ["1"])[0]
                return [
                    {
                        "id": self.estado._nuevo_id(),
                        "courseid": int(courseid),
                        "type": "self",
                        "name": "Self enrolment",
                        "status": 1,
                        "enrolstartdate": 0,
                        "enrolenddate": 0,
                    }
                ]
            if wsfunction == "core_user_get_users_by_field":
                return self._obtener_usuarios_por_campo(params)
            if wsfunction == "core_user_get_users":
                return {"users": [], "total": 0}
            if wsfunction == "core_user_create_users":
                return self._crear_usuarios(params)
            if wsfunction == "core_user_update_users":
                return self._actualizar_usuarios(params)
            if wsfunction == "core_user_delete_users":
                return self._eliminar_usuarios(params)
            if wsfunction == "core_role_assign_role":
                return []
            if wsfunction == "enrol_manual_enrol_users":
                return self._enrol_manual(params, "enrol")
            if wsfunction == "enrol_manual_unenrol_users":
                return self._enrol_manual(params, "unenrol")
            if wsfunction == "core_enrol_get_enrolled_users":
                return self._matriculados_en(params)
            logger.warning("wsfunction desconocida: %s", wsfunction)
            return UNKNOWN_WS_RESULT

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------

    def _crear_categorias(self, params) -> list[dict]:
        resultado = []
        for cat in _parametros_desindexados(params, "categories"):
            nid = self.estado._nuevo_id()
            self.estado.categorias.append(
                {
                    "id": nid,
                    "name": cat.get("name", ""),
                    "idnumber": cat.get("idnumber", ""),
                    "parent": int(cat.get("parent", "0") or 0),
                    "visible": 1,
                }
            )
            resultado.append({"id": nid})
        return resultado

    def _actualizar_categorias(self, params) -> list[dict]:
        for cat in _parametros_desindexados(params, "categories"):
            nid = int(cat["id"])
            for c in self.estado.categorias:
                if c["id"] == nid:
                    if "name" in cat:
                        c["name"] = cat["name"]
                    if "idnumber" in cat:
                        c["idnumber"] = cat["idnumber"]
                    if "parent" in cat:
                        c["parent"] = int(cat["parent"])
        return []

    def _eliminar_categorias(self, params) -> list[dict]:
        ids = {
            int(v[0])
            for k, v in params.items()
            if k.startswith("categories[") and k.endswith("[id]")
        }
        self.estado.categorias = [c for c in self.estado.categorias if c["id"] not in ids]
        return []

    # ------------------------------------------------------------------
    # Cursos
    # ------------------------------------------------------------------

    def _crear_cursos(self, params) -> list[dict]:
        resultado = []
        for curso in _parametros_desindexados(params, "courses"):
            nid = self.estado._nuevo_id()
            self.estado.cursos.append(
                {
                    "id": nid,
                    "shortname": curso.get("shortname", ""),
                    "fullname": curso.get("fullname", ""),
                    "categoryid": int(curso.get("categoryid", "0") or 0),
                    "visible": int(curso.get("visible", "1") or 1),
                    "format": curso.get("format", "topics"),
                }
            )
            resultado.append({"id": nid})
        return resultado

    def _actualizar_cursos(self, params) -> list[dict]:
        for curso in _parametros_desindexados(params, "courses"):
            nid = int(curso["id"])
            for c in self.estado.cursos:
                if c["id"] == nid:
                    for campo in ("shortname", "fullname", "visible", "format"):
                        if campo in curso:
                            c[campo] = curso[campo]
                    if "categoryid" in curso:
                        c["categoryid"] = int(curso["categoryid"])
        return []

    def _eliminar_cursos(self, params) -> list[dict]:
        ids = {int(v[0]) for k, v in params.items() if k.startswith("courseids[")}
        self.estado.cursos = [c for c in self.estado.cursos if c["id"] not in ids]
        return []

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    def _obtener_usuarios_por_campo(self, params) -> list[dict]:
        campo = params.get("field", [""])[0]
        valores = [v[0] for k, v in params.items() if k.startswith("values[")]
        if campo not in ("username", "email", "idnumber"):
            return []
        indexado = self.estado.usuarios_por(campo)
        return [
            {**u, "lastlogin": u.get("lastlogin", 0)}
            for v in valores
            if v in indexado
            for u in [indexado[v]]
        ]

    def _crear_usuarios(self, params) -> list[dict]:
        resultado = []
        for user in _parametros_desindexados(params, "users"):
            nid = self.estado._nuevo_id()
            self.estado.usuarios.append(
                {
                    "id": nid,
                    "username": user.get("username", ""),
                    "firstname": user.get("firstname", ""),
                    "lastname": user.get("lastname", ""),
                    "email": user.get("email", ""),
                    "idnumber": user.get("idnumber", ""),
                    "city": user.get("city", ""),
                    "auth": user.get("auth", "manual"),
                }
            )
            resultado.append({"id": nid})
        return resultado

    def _actualizar_usuarios(self, params) -> list[dict]:
        for user in _parametros_desindexados(params, "users"):
            nid = int(user["id"])
            for u in self.estado.usuarios:
                if u["id"] == nid:
                    for campo in ("username", "email", "firstname", "lastname", "auth"):
                        if campo in user:
                            u[campo] = user[campo]
        return []

    def _eliminar_usuarios(self, params) -> list[dict]:
        ids = {int(v[0]) for k, v in params.items() if k.startswith("userids[")}
        self.estado.usuarios = [u for u in self.estado.usuarios if u["id"] not in ids]
        return []

    # ------------------------------------------------------------------
    # Matriculación
    # ------------------------------------------------------------------

    def _enrol_manual(self, params, accion: str) -> list[dict]:
        for enrol in _parametros_desindexados(params, "enrolments"):
            self.estado.matriculas.append(
                {
                    "userid": int(enrol.get("userid", "0")),
                    "courseid": int(enrol.get("courseid", "0")),
                    "roleid": int(enrol.get("roleid", "5")),
                    "accion": accion,
                }
            )
        return []

    def _matriculados_en(self, params) -> list[dict]:
        try:
            courseid = int(params.get("courseid", ["0"])[0])
        except ValueError:
            courseid = 0
        usuarios_por_id = {u["id"]: u for u in self.estado.usuarios}
        matriculados = [
            m
            for m in self.estado.matriculas
            if m["courseid"] == courseid and m["accion"] == "enrol"
        ]
        return [
            {
                "id": m["userid"],
                "username": usuarios_por_id.get(m["userid"], {}).get("username", ""),
                "email": usuarios_por_id.get(m["userid"], {}).get("email", ""),
                "roles": [],
            }
            for m in matriculados
        ]

    def log_message(self, fmt: str, *args) -> None:
        logger.info("  -> %s", fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Moodle simulado para SIAUGESMAT")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8800)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    estado = EstadoMoodle()
    servidor = ThreadingHTTPServer((args.host, args.port), ManejadorMoodle)
    servidor.estado = estado  # type: ignore[attr-defined]
    logger.info("Moodle simulado escuchando en http://%s:%d", args.host, args.port)
    logger.info("Presiona Ctrl+C para detener.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
