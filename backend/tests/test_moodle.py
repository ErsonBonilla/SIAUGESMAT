"""
Pruebas unitarias del cliente MoodleService.

Se verifica la correcta construcción de parámetros, el manejo de respuestas
exitosas, errores y reintentos, utilizando un cliente HTTP simulado.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.adaptador_moodle import AdaptadorMoodle
from app.services.errores_moodle import ErrorApiMoodle
from app.services.operaciones_moodle import ServicioMoodle


# ---------------------------------------------------------------------------
# Fixture: servicio con cliente HTTP simulado y adapter mockeado
# ---------------------------------------------------------------------------
@pytest.fixture
def moodle_service():
    """Crea una instancia de MoodleService con adapter mockeado."""
    mock_adapter = AsyncMock(spec=AdaptadorMoodle)
    mock_adapter.construir_parametros_matriculacion_curso.return_value = None
    service = ServicioMoodle(
        token="fake_token", base_url="http://fake.moodle.com", adapter=mock_adapter
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    service._cliente = mock_client
    service._limitador_tasa = AsyncMock()
    return service, mock_adapter

    # ---------------------------------------------------------------------------
    # Método _solicitar – éxito
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_solicitar_success(moodle_service):
    """Una petición correcta debe retornar los datos JSON de la respuesta."""
    service, _ = moodle_service
    expected = {"courses": [{"id": 1, "shortname": "TEST_101"}]}
    fake_response = MagicMock()
    fake_response.json.return_value = expected
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    result = await service._solicitar("core_course_get_courses", {"criteria[0][key]": "shortname"})
    assert result == expected
    service._cliente.post.assert_called_once()

    # ---------------------------------------------------------------------------
    # Método _solicitar – error de Moodle
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_solicitar_moodle_error(moodle_service):
    """Un error de la API de Moodle se re-lanza tras agotar los reintentos.

    `_solicitar_con_reintento` usa `reraise=True`, así que tras consumir los
    intentos la excepción original (`ErrorApiMoodle`) se propaga tal cual, sin
    envolver en `RetryError`.
    """
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = {"error": "Curso no encontrado", "errorcode": "notfound"}
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    with pytest.raises(ErrorApiMoodle) as exc_info:
        await service._solicitar("core_course_get_courses", {})
    assert exc_info.value.codigo_error == "notfound"
    assert service._cliente.post.call_count == settings.MOODLE_MAX_RETRIES

    # ---------------------------------------------------------------------------
    # Reintentos ante error HTTP
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_solicitar_retry_on_http_error(moodle_service):
    """La petición debe reintentarse cuando ocurre un httpx.HTTPError."""
    service, _ = moodle_service
    fake_response_success = MagicMock()
    fake_response_success.json.return_value = {"ok": True}
    fake_response_success.raise_for_status.return_value = None

    service._cliente.post.side_effect = [
        httpx.HTTPError("Timeout"),
        httpx.HTTPError("Timeout"),
        fake_response_success,
    ]

    result = await service._solicitar("core_webservice_get_site_info", {})
    assert result == {"ok": True}
    assert service._cliente.post.call_count == 3

    # ---------------------------------------------------------------------------
    # Categorías
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_categories(moodle_service):
    """La creación de categorías debe enviar los parámetros correctos."""
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 5, "name": "IDEAD"}]
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    categories = [{"name": "IDEAD", "idnumber": "IDE", "parent": 0}]
    result = await service.crear_categorias(categories)
    assert result[0]["id"] == 5
    call_args = service._cliente.post.call_args[1]["data"]
    assert call_args["wsfunction"] == "core_course_create_categories"
    assert call_args["categories[0][name]"] == "IDEAD"
    assert call_args["categories[0][idnumber]"] == "IDE"
    assert call_args["categories[0][parent]"] == 0


@pytest.mark.asyncio
async def test_get_categories_by_idnumber(moodle_service):
    """Debe obtener todas las categorías y filtrar por idnumber en Python."""
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = [
        {"id": 1, "idnumber": "IDE_0105"},
        {"id": 2, "idnumber": "OTHER"},
    ]
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    result = await service.obtener_categorias(idnumber="IDE_0105")
    assert len(result) == 1
    assert result[0]["idnumber"] == "IDE_0105"
    params = service._cliente.post.call_args[1]["data"]
    assert params["wsfunction"] == "core_course_get_categories"
    assert "criteria" not in params


@pytest.mark.asyncio
async def test_create_categories_invalidates_cache(moodle_service):
    """Tras crear categorías, el caché debe invalidarse para que la resolución
    de padres de una categoría recién creada la encuentre (jerarquía correcta)."""
    service, _ = moodle_service

    def _resp(payload):
        r = MagicMock()
        r.json.return_value = payload
        r.raise_for_status.return_value = None
        return r

        # (0) get_categories() inicial (orquestador): vacío
        # (1) create padre -> respuesta OK
        # (2) get_categories() re-fetch tras invalidar -> ve el padre recién creado
        # (3) create hijo -> respuesta OK

    service._cliente.post.side_effect = [
        _resp([]),
        _resp([{"id": 5, "idnumber": "IBA_0992"}]),
        _resp([{"id": 5, "idnumber": "IBA_0992"}]),
        _resp([]),
    ]

    await service.obtener_categorias()
    await service.crear_categorias(
        [
            {
                "name": "Programa",
                "idnumber": "IBA_0992",
                "parent": "0",
            }
        ]
    )
    await service.crear_categorias(
        [
            {
                "name": "Semestre I",
                "idnumber": "IBA_0992_sI",
                "parent": "IBA_0992",
            }
        ]
    )

    last_call = service._cliente.post.call_args_list[-1][1]["data"]
    assert last_call["categories[0][parent]"] == 5

    # ---------------------------------------------------------------------------
    # Cursos
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_courses(moodle_service):
    """Crear cursos resolviendo categoryidnumber a categoryid numérico."""
    service, mock_adapter = moodle_service
    fake_cat = MagicMock()
    fake_cat.json.return_value = [{"id": 1, "idnumber": "CAT_1"}]
    fake_cat.raise_for_status.return_value = None
    fake_create = MagicMock()
    fake_create.json.return_value = [{"id": 10, "shortname": "CUR_01"}]
    fake_create.raise_for_status.return_value = None
    service._cliente.post.side_effect = [fake_cat, fake_create]

    courses = [
        {
            "shortname": "CUR_01",
            "fullname": "Curso 1",
            "categoryidnumber": "CAT_1",
            "format": "onetopic",
            "visible": 1,
        }
    ]
    result = await service.crear_cursos(courses)
    assert len(result) == 1
    mock_adapter.construir_parametros_matriculacion_curso.assert_called_once()
    last_call = service._cliente.post.call_args_list[-1][1]["data"]
    assert last_call["courses[0][shortname]"] == "CUR_01"
    assert last_call["courses[0][categoryid]"] == 1
    assert last_call["courses[0][format]"] == "onetopic"
    assert last_call["courses[0][visible]"] == 1


@pytest.mark.asyncio
async def test_update_courses(moodle_service):
    """Actualizar cursos resolviendo shortname a ID numérico."""
    service, mock_adapter = moodle_service
    mock_adapter.obtener_cursos.return_value = [{"id": 5, "shortname": "OLD"}]
    fake_upd = MagicMock()
    fake_upd.json.return_value = None
    fake_upd.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_upd

    await service.actualizar_cursos([{"shortname": "OLD", "visible": 0}])
    last_call = service._cliente.post.call_args_list[-1][1]["data"]
    assert last_call["courses[0][id]"] == 5
    assert last_call["courses[0][visible]"] == 0


@pytest.mark.asyncio
async def test_delete_courses(moodle_service):
    """Eliminar cursos resolviendo shortnames a IDs numéricos (en lote)."""
    service, mock_adapter = moodle_service
    mock_adapter.obtener_cursos.return_value = [
        {"id": 1, "shortname": "DEL1"},
        {"id": 2, "shortname": "DEL2"},
    ]
    with patch.object(service, "_solicitar", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = None
        await service.eliminar_cursos(["DEL1", "DEL2"])

    params = mock_req.call_args[0][1]
    assert params["courseids[0]"] == 1
    assert params["courseids[1]"] == 2

    # ---------------------------------------------------------------------------
    # Usuarios
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_users(moodle_service):
    """Crear usuarios con los campos obligatorios."""
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 100, "username": "juan"}]
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    users = [
        {
            "username": "juan",
            "firstname": "Juan",
            "lastname": "Pérez",
            "email": "juan@ut.edu.co",
            "password": "changeme",
        }
    ]
    result = await service.crear_usuarios(users)
    assert result[0]["id"] == 100
    params = service._cliente.post.call_args[1]["data"]
    assert params["users[0][username]"] == "juan"
    assert params["users[0][email]"] == "juan@ut.edu.co"


@pytest.mark.asyncio
async def test_delete_users_by_username(moodle_service):
    """Eliminar usuarios resolviendo usernames a IDs numéricos."""
    service, _ = moodle_service
    fake_get = MagicMock()
    fake_get.json.return_value = [{"id": 10, "username": "juan"}, {"id": 20, "username": "maria"}]
    fake_get.raise_for_status.return_value = None
    fake_del = MagicMock()
    fake_del.json.return_value = None
    fake_del.raise_for_status.return_value = None
    service._cliente.post.side_effect = [fake_get, fake_del]

    await service.eliminar_usuarios(["juan", "maria"])
    last_call = service._cliente.post.call_args_list[-1][1]["data"]
    assert last_call["userids[0]"] == 10
    assert last_call["userids[1]"] == 20


@pytest.mark.asyncio
async def test_get_users(moodle_service):
    """Buscar usuarios por email usando core_user_get_users_by_field."""
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 1, "email": "a@b.com"}]
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    result = await service.obtener_usuarios("email", ["a@b.com"])
    assert len(result) == 1
    assert result[0]["email"] == "a@b.com"
    params = service._cliente.post.call_args[1]["data"]
    assert params["field"] == "email"
    assert params["values[0]"] == "a@b.com"


@pytest.mark.asyncio
async def test_get_users_chunks_large_values(moodle_service):
    """Un lote grande se fragmenta (Moodle trunca respuestas grandes)."""
    service, _ = moodle_service
    calls = []

    async def fake_solicitar(wsfunction, params, use_post=False, timeout=None):
        calls.append(params)
        n = len(params) - 1
        return [{"username": params[f"values[{i}]"], "id": i} for i in range(n)]

    service._solicitar = fake_solicitar
    values = [f"u{i}" for i in range(250)]
    result = await service.obtener_usuarios("username", values)
    assert len(result) == 250
    assert [len(c) - 1 for c in calls] == [100, 100, 50]
    assert calls[0]["values[0]"] == "u0"
    assert calls[2]["values[0]"] == "u200"


@pytest.mark.asyncio
async def test_get_users_invalid_chunk_falls_back_per_value(moodle_service):
    """Un lote rechazado por invalidparameter se reconsulta valor a valor."""
    service, _ = moodle_service
    calls = []

    async def fake_solicitar(wsfunction, params, use_post=False, timeout=None):
        calls.append(params)
        n = len(params) - 1
        if n > 1:
            raise ErrorApiMoodle("invalid", "invalidparameter")
        return [{"username": params.get("values[0]"), "id": 1}]

    service._solicitar = fake_solicitar
    result = await service.obtener_usuarios("username", ["a", "b", "c"])
    assert len(result) == 3
    assert len(calls) == 4  # 1 lote fallido + 3 individuales

    # ---------------------------------------------------------------------------
    # Matriculación
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrol_users(moodle_service):
    """Matricular usuarios resolviendo usernames y cursos por shortname."""
    service, mock_adapter = moodle_service
    mock_adapter.obtener_cursos.return_value = [{"shortname": "CURSO1", "id": 200}]

    async def mock_get(*args, **kwargs):
        params = kwargs.get("data", {})
        wsfunction = params.get("wsfunction")
        if wsfunction == "core_user_get_users_by_field":
            return MagicMock(
                json=lambda: [{"username": "teacher1", "id": 10}],
                raise_for_status=lambda: None,
            )
        if wsfunction == "enrol_manual_enrol_users":
            return MagicMock(json=lambda: None, raise_for_status=lambda: None)
        return MagicMock(json=dict, raise_for_status=lambda: None)

    service._cliente.post.side_effect = mock_get

    enrolments = [{"username": "teacher1", "course_shortname": "CURSO1", "role": "editingteacher"}]
    await service.matricular_usuarios(enrolments)

    last_call_params = service._cliente.post.call_args[1]["data"]
    assert last_call_params["wsfunction"] == "enrol_manual_enrol_users"
    assert last_call_params["enrolments[0][userid]"] == 10
    assert last_call_params["enrolments[0][courseid]"] == 200
    assert last_call_params["enrolments[0][roleid]"] == 3  # editingteacher


@pytest.mark.asyncio
async def test_enrol_users_resolves_missing_username_by_email(moodle_service):
    """Si el username ETL no existe, la matriculación resuelve por email."""
    service, mock_adapter = moodle_service
    mock_adapter.obtener_cursos.return_value = [{"shortname": "CURSO1", "id": 200}]

    async def mock_get(*args, **kwargs):
        params = kwargs.get("data", {})
        wsfunction = params.get("wsfunction")
        if wsfunction == "core_user_get_users_by_field":
            if params.get("field") == "email":
                return MagicMock(
                    json=lambda: [{"username": "realuser", "id": 10, "email": "etluser@ut.edu.co"}],
                    raise_for_status=lambda: None,
                )
            return MagicMock(json=lambda: [], raise_for_status=lambda: None)
        if wsfunction == "enrol_manual_enrol_users":
            return MagicMock(json=lambda: None, raise_for_status=lambda: None)
        return MagicMock(json=dict, raise_for_status=lambda: None)

    service._cliente.post.side_effect = mock_get

    result = await service.matricular_usuarios(
        [
            {
                "username": "etluser",
                "course_shortname": "CURSO1",
                "role": "editingteacher",
                "email": "etluser@ut.edu.co",
            }
        ]
    )
    assert result["success"] is True
    params = service._cliente.post.call_args_list[-1][1]["data"]
    assert params["enrolments[0][userid]"] == 10

    # ---------------------------------------------------------------------------
    # Delegación al adapter (self enrolment)
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enable_self_enrolment_delegates_to_adapter(moodle_service):
    """enable_self_enrolment debe delegar en el adapter."""
    service, mock_adapter = moodle_service
    mock_adapter.habilitar_automatriculacion.return_value = {"id": 99}

    result = await service.habilitar_automatriculacion(500)
    assert result["id"] == 99
    mock_adapter.habilitar_automatriculacion.assert_awaited_once_with(500, service._solicitar)


@pytest.mark.asyncio
async def test_get_courses_delegates_to_adapter(moodle_service):
    """get_courses debe delegar en el adapter."""
    service, mock_adapter = moodle_service
    mock_adapter.obtener_cursos.return_value = [{"id": 1, "shortname": "T1"}]

    result = await service.obtener_cursos(shortname="T1")
    assert result[0]["shortname"] == "T1"
    mock_adapter.obtener_cursos.assert_awaited_once_with("T1", service._solicitar)


@pytest.mark.asyncio
async def test_get_courses_bare_delegates_to_adapter(moodle_service):
    """get_courses sin argumentos debe delegar en el adapter."""
    service, mock_adapter = moodle_service
    mock_adapter.obtener_cursos.return_value = []

    result = await service.obtener_cursos()
    assert result == []
    mock_adapter.obtener_cursos.assert_awaited_once_with(None, service._solicitar)

    # ---------------------------------------------------------------------------
    # Rate limiting
    # ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_called(moodle_service):
    """Cada llamada a _solicitar debe pasar por el rate limiter."""
    service, _ = moodle_service
    mock_limiter = AsyncMock()
    service._limitador_tasa = mock_limiter
    fake_response = MagicMock()
    fake_response.json.return_value = {}
    fake_response.raise_for_status.return_value = None
    service._cliente.post.return_value = fake_response

    await service._solicitar("core_webservice_get_site_info", {})
    mock_limiter.adquirir.assert_called_once()
