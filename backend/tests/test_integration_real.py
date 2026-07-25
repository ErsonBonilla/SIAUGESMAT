"""
Prueba de integración REAL contra Moodle 3.9.

Verifica que las 6 operaciones críticas del ETL funcionan
correctamente contra la instancia de Moodle configurada en .env:
  - Crear y eliminar categoría
  - Crear y eliminar curso (sin enrolment_1, con categoryid numérico)
  - Crear y eliminar usuario

Requisitos:
  - MOODLE_URL__DISTANCIA, MOODLE_TOKEN__DISTANCIA, MOODLE_VERSION__DISTANCIA
    configuradas en el archivo .env

Ejecución:
  pytest -m integration -v          # solo tests de integración
  pytest -m "not integration" -v    # sin tests de integración
  pytest -v                         # todos los tests
"""

import asyncio
import logging
import uuid

import pytest

from app.core.config import settings
from app.services.moodle import MoodleService

pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def _get_service():
    """Obtiene una instancia de MoodleService para DISTANCIA."""
    try:
        cfg = settings.get_moodle_config("DISTANCIA")
    except ValueError:
        pytest.skip("MOODLE_URL__DISTANCIA no configurada en .env")
    return MoodleService(
        token=cfg["token"],
        base_url=cfg["url"],
        version=cfg["version"],
    )


class TestRealMoodleCategoria:
    @pytest.mark.asyncio
    async def test_crear_y_eliminar_categoria(self):
        """Crea una categoría, verifica que existe, y la elimina."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        cat_idn = f"TEST_INT_CAT_{uid}"

        try:
            # Crear
            await ms.create_categories([{
                "name": f"CAT INTEGRACION {uid}",
                "idnumber": cat_idn,
                "parent": 0,
            }])
            cats = await ms.get_categories(idnumber=cat_idn)
            assert cats, "La categoría no se encontró después de crearla"

            # Eliminar
            await ms.delete_category(int(cats[0]["id"]), recursive=True)
            cats2 = await ms.get_categories(idnumber=cat_idn)
            assert not cats2, "La categoría no se eliminó correctamente"
        finally:
            await ms.close()


class TestRealMoodleCurso:
    @pytest.mark.asyncio
    async def test_crear_y_eliminar_curso(self):
        """Crea un curso sin enrolment_1, verifica, y lo elimina."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        cat_idn = f"TEST_INT_CAT_{uid}"
        sn = f"TEST_INT_CURSO_{uid}"

        try:
            # Crear categoría padre primero
            await ms.create_categories([{
                "name": f"CAT INT {uid}",
                "idnumber": cat_idn,
                "parent": 0,
            }])

            # Crear curso
            r = await ms.create_courses([{
                "shortname": sn,
                "fullname": f"CURSO INTEGRACION {uid}",
                "categoryidnumber": cat_idn,
                "format": "onetopic",
                "visible": 1,
            }])
            assert r, "create_courses no devolvió resultado"
            assert r[0].get("id"), "El curso creado no tiene ID"

            # Verificar que existe via get_courses(shortname=...)
            courses = await ms.get_courses(shortname=sn)
            assert courses, "get_courses(shortname) no encontró el curso"
            assert courses[0]["id"] == r[0]["id"]

            # Eliminar
            await ms.delete_courses([sn])
            courses2 = await ms.get_courses(shortname=sn)
            assert not courses2, "El curso no se eliminó"

            # Limpiar categoría
            cats = await ms.get_categories(idnumber=cat_idn)
            if cats:
                await ms.delete_category(int(cats[0]["id"]), recursive=True)
        finally:
            await ms.close()


class TestRealMoodleUsuario:
    @pytest.mark.asyncio
    async def test_crear_y_eliminar_usuario(self):
        """Crea un usuario, verifica, y lo elimina."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        username = f"testint_{uid}"

        try:
            # Crear
            await ms.create_users([{
                "username": username,
                "firstname": "Test",
                "lastname": f"Integracion{uid}",
                "email": f"{username}@test.com",
                "createpassword": True,
            }])
            users = await ms.get_users("username", [username])
            assert users, "El usuario no se encontró después de crearlo"
            assert users[0]["username"] == username

            # Eliminar
            await ms.delete_users([username])
            users2 = await ms.get_users("username", [username])
            assert not users2, "El usuario no se eliminó"
        finally:
            await ms.close()


class TestRealMoodleFlujoCompleto:
    @pytest.mark.asyncio
    async def test_flujo_completo(self):
        """Las 6 operaciones en secuencia: crear 3 entidades y eliminar las 3."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        cat_idn = f"TEST_INT_FLOW_{uid}"
        sn = f"TEST_INT_FLOW_{uid}"
        username = f"testflow_{uid}"

        try:
            # 1. Crear categoría
            await ms.create_categories([{
                "name": f"FLOW CAT {uid}",
                "idnumber": cat_idn,
                "parent": 0,
            }])
            cats = await ms.get_categories(idnumber=cat_idn)
            assert cats, "1. Crear categoría falló"

            # 2. Crear curso
            r = await ms.create_courses([{
                "shortname": sn,
                "fullname": f"FLOW CURSO {uid}",
                "categoryidnumber": cat_idn,
                "format": "onetopic",
                "visible": 1,
            }])
            assert r and r[0].get("id"), "2. Crear curso falló"

            # 3. Crear usuario
            await ms.create_users([{
                "username": username,
                "firstname": "Flow",
                "lastname": uid,
                "email": f"{username}@test.com",
                "createpassword": True,
            }])
            users = await ms.get_users("username", [username])
            assert users, "3. Crear usuario falló"

            # 4. Eliminar usuario
            await ms.delete_users([username])
            users2 = await ms.get_users("username", [username])
            assert not users2, "4. Eliminar usuario falló"

            # 5. Eliminar curso
            await ms.delete_courses([sn])
            courses = await ms.get_courses(shortname=sn)
            assert not courses, "5. Eliminar curso falló"

            # 6. Eliminar categoría
            cats = await ms.get_categories(idnumber=cat_idn)
            if cats:
                await ms.delete_category(int(cats[0]["id"]), recursive=True)
                cats2 = await ms.get_categories(idnumber=cat_idn)
                assert not cats2, "6. Eliminar categoría falló"
        finally:
            await ms.close()


class TestRealMoodleCursoConTemplate:
    @pytest.mark.asyncio
    async def test_crear_curso_sin_template(self):
        """Crea un curso sin templatecourse (el caso base que SI funciona)."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        cat_idn = f"TEST_INT_NTPL_{uid}"
        sn = f"TEST_INT_NTPL_{uid}"

        try:
            await ms.create_categories([{
                "name": f"CAT NTPL {uid}",
                "idnumber": cat_idn,
                "parent": 0,
            }])

            r = await ms.create_courses([{
                "shortname": sn,
                "fullname": f"CURSO NTPL {uid}",
                "categoryidnumber": cat_idn,
                "format": "onetopic",
                "visible": 1,
            }])
            assert r and r[0].get("id"), "create_courses sin template falló"

            courses = await ms.get_courses(shortname=sn)
            assert courses, "get_courses(shortname) no encontró el curso"

            await ms.delete_courses([sn])
            courses2 = await ms.get_courses(shortname=sn)
            assert not courses2, "El curso no se eliminó"

            cats = await ms.get_categories(idnumber=cat_idn)
            if cats:
                await ms.delete_category(int(cats[0]["id"]), recursive=True)
        finally:
            await ms.close()

    @pytest.mark.asyncio
    async def test_crear_curso_con_import_content(self):
        """Crea curso vacío + importa contenido con core_course_import_course (activa enrol manual)."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        cat_idn = f"TEST_INT_IMP_{uid}"
        sn = f"TEST_INT_IMP_{uid}"

        try:
            await ms.create_categories([{
                "name": f"CAT IMP {uid}",
                "idnumber": cat_idn,
                "parent": 0,
            }])

            templates = await ms.get_courses(shortname=settings.DEFAULT_COURSE_TEMPLATE)
            assert templates, f"Template '{settings.DEFAULT_COURSE_TEMPLATE}' no existe"
            template_id = int(templates[0]["id"])

            # Paso 1: crear curso vacío (activa instancia enrol manual)
            r = await ms.create_courses([{
                "shortname": sn,
                "fullname": f"CURSO IMP {uid}",
                "categoryidnumber": cat_idn,
                "format": "onetopic",
                "visible": 1,
            }])
            assert r and r[0].get("id"), "create_courses sin template falló"
            course_id = int(r[0]["id"])

            # Paso 2: importar contenido de la plantilla
            await ms.import_course_content(from_id=template_id, to_id=course_id)
            logger.info(f"Plantilla {template_id} importada a curso {course_id}")

            await ms.delete_courses([sn])
            courses2 = await ms.get_courses(shortname=sn)
            assert not courses2, "El curso no se eliminó"

            cats = await ms.get_categories(idnumber=cat_idn)
            if cats:
                await ms.delete_category(int(cats[0]["id"]), recursive=True)
        finally:
            await ms.close()

    @pytest.mark.asyncio
    async def test_duplicate_course_endpoint(self):
        """Verifica que duplicate_course existe y funciona (aunque no activa enrol manual)."""
        ms = _get_service()
        uid = uuid.uuid4().hex[:6]
        cat_idn = f"TEST_INT_DUP_{uid}"
        sn = f"TEST_INT_DUP_{uid}"

        try:
            await ms.create_categories([{
                "name": f"CAT DUP {uid}",
                "idnumber": cat_idn,
                "parent": 0,
            }])
            cats = await ms.get_categories(idnumber=cat_idn)
            cat_id = int(cats[0]["id"])

            templates = await ms.get_courses(shortname=settings.DEFAULT_COURSE_TEMPLATE)
            template_id = int(templates[0]["id"])

            r = await ms.duplicate_course(
                from_id=template_id,
                fullname=f"CURSO DUP {uid}",
                shortname=sn,
                categoryid=cat_id,
                visible=1,
            )
            assert r and r.get("id"), f"duplicate_course falló"

            await ms.delete_courses([sn])
            cats = await ms.get_categories(idnumber=cat_idn)
            if cats:
                await ms.delete_category(int(cats[0]["id"]), recursive=True)
        finally:
            await ms.close()
