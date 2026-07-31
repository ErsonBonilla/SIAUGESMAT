"""
Pruebas unitarias del cliente MoodleService.

Se verifica la correcta construcción de parámetros, el manejo de respuestas
exitosas, errores y reintentos, utilizando un cliente HTTP simulado.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from tenacity import RetryError

from app.services.moodle_errors import MoodleAPIError
from app.services.moodle_operations import MoodleService
from app.services.moodle_adapter import MoodleAdapter
from app.core.config import settings


# ---------------------------------------------------------------------------
# Fixture: servicio con cliente HTTP simulado y adapter mockeado
# ---------------------------------------------------------------------------
@pytest.fixture
def moodle_service():
    """Crea una instancia de MoodleService con adapter mockeado."""
    mock_adapter = AsyncMock(spec=MoodleAdapter)
    mock_adapter.build_create_course_enrolment_params.return_value = None
    service = MoodleService(token="fake_token", base_url="http://fake.moodle.com", adapter=mock_adapter)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    service._client = mock_client
    return service, mock_adapter


# ---------------------------------------------------------------------------
# Método _request – éxito
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_request_success(moodle_service):
    """Una petición correcta debe retornar los datos JSON de la respuesta."""
    service, _ = moodle_service
    expected = {"courses": [{"id": 1, "shortname": "TEST_101"}]}
    fake_response = MagicMock()
    fake_response.json.return_value = expected
    fake_response.raise_for_status.return_value = None
    service._client.get.return_value = fake_response

    result = await service._request("core_course_get_courses", {"criteria[0][key]": "shortname"})
    assert result == expected
    service._client.get.assert_called_once()


# ---------------------------------------------------------------------------
# Método _request – error de Moodle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_request_moodle_error(moodle_service):
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = {"error": "Curso no encontrado", "errorcode": "notfound"}
    fake_response.raise_for_status.return_value = None
    service._client.get.return_value = fake_response

    with pytest.raises(RetryError) as exc_info:
        await service._request("core_course_get_courses", {})
    # La excepción original está en exc_info.value.__cause__
    assert isinstance(exc_info.value.__cause__, MoodleAPIError)
    
# ---------------------------------------------------------------------------
# Reintentos ante error HTTP
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_request_retry_on_http_error(moodle_service):
    """La petición debe reintentarse cuando ocurre un httpx.HTTPError."""
    service, _ = moodle_service
    fake_response_success = MagicMock()
    fake_response_success.json.return_value = {"ok": True}
    fake_response_success.raise_for_status.return_value = None

    service._client.get.side_effect = [
        httpx.HTTPError("Timeout"),
        httpx.HTTPError("Timeout"),
        fake_response_success,
    ]

    result = await service._request("core_webservice_get_site_info", {})
    assert result == {"ok": True}
    assert service._client.get.call_count == 3


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
    service._client.get.return_value = fake_response

    categories = [{"name": "IDEAD", "idnumber": "IDE", "parent": 0}]
    result = await service.create_categories(categories)
    assert result[0]["id"] == 5
    call_args = service._client.get.call_args[1]["params"]
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
    service._client.get.return_value = fake_response

    result = await service.get_categories(idnumber="IDE_0105")
    assert len(result) == 1
    assert result[0]["idnumber"] == "IDE_0105"
    params = service._client.get.call_args[1]["params"]
    assert params["wsfunction"] == "core_course_get_categories"
    assert "criteria" not in params


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
    service._client.get.side_effect = [fake_cat, fake_create]

    courses = [{
        "shortname": "CUR_01",
        "fullname": "Curso 1",
        "categoryidnumber": "CAT_1",
        "format": "onetopic",
        "visible": 1,
    }]
    result = await service.create_courses(courses)
    assert len(result) == 1
    mock_adapter.build_create_course_enrolment_params.assert_called_once()
    last_call = service._client.get.call_args_list[-1][1]["params"]
    assert last_call["courses[0][shortname]"] == "CUR_01"
    assert last_call["courses[0][categoryid]"] == 1
    assert last_call["courses[0][format]"] == "onetopic"
    assert last_call["courses[0][visible]"] == 1


@pytest.mark.asyncio
async def test_update_courses(moodle_service):
    """Actualizar cursos resolviendo shortname a ID numérico."""
    service, mock_adapter = moodle_service
    mock_adapter.get_courses.return_value = [{"id": 5, "shortname": "OLD"}]
    fake_upd = MagicMock()
    fake_upd.json.return_value = None
    fake_upd.raise_for_status.return_value = None
    service._client.get.return_value = fake_upd

    await service.update_courses([{"shortname": "OLD", "visible": 0}])
    last_call = service._client.get.call_args_list[-1][1]["params"]
    assert last_call["courses[0][id]"] == 5
    assert last_call["courses[0][visible]"] == 0


@pytest.mark.asyncio
async def test_delete_courses(moodle_service):
    """Eliminar cursos resolviendo shortnames a IDs numéricos."""
    service, mock_adapter = moodle_service
    mock_adapter.get_courses.side_effect = [
        [{"id": 1}],
        [{"id": 2}],
    ]
    with patch.object(service, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = None
        await service.delete_courses(["DEL1", "DEL2"])

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
    service._client.get.return_value = fake_response

    users = [{
        "username": "juan",
        "firstname": "Juan",
        "lastname": "Pérez",
        "email": "juan@ut.edu.co",
        "password": "changeme",
    }]
    result = await service.create_users(users)
    assert result[0]["id"] == 100
    params = service._client.get.call_args[1]["params"]
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
    service._client.get.side_effect = [fake_get, fake_del]

    await service.delete_users(["juan", "maria"])
    last_call = service._client.get.call_args_list[-1][1]["params"]
    assert last_call["userids[0]"] == 10
    assert last_call["userids[1]"] == 20


@pytest.mark.asyncio
async def test_get_users(moodle_service):
    """Buscar usuarios por email usando core_user_get_users_by_field."""
    service, _ = moodle_service
    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 1, "email": "a@b.com"}]
    fake_response.raise_for_status.return_value = None
    service._client.get.return_value = fake_response

    result = await service.get_users("email", ["a@b.com"])
    assert len(result) == 1
    assert result[0]["email"] == "a@b.com"
    params = service._client.get.call_args[1]["params"]
    assert params["field"] == "email"
    assert params["values[0]"] == "a@b.com"


# ---------------------------------------------------------------------------
# Matriculación
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_enrol_users(moodle_service):
    """Matricular usuarios resolviendo usernames y cursos por shortname."""
    service, mock_adapter = moodle_service
    mock_adapter.get_courses.return_value = [{"shortname": "CURSO1", "id": 200}]

    async def mock_get(*args, **kwargs):
        params = kwargs.get("params", {})
        wsfunction = params.get("wsfunction")
        if wsfunction == "core_user_get_users_by_field":
            return MagicMock(
                json=lambda: [{"username": "teacher1", "id": 10}],
                raise_for_status=lambda: None,
            )
        elif wsfunction == "enrol_manual_enrol_users":
            return MagicMock(json=lambda: None, raise_for_status=lambda: None)
        return MagicMock(json=lambda: {}, raise_for_status=lambda: None)

    service._client.get.side_effect = mock_get

    enrolments = [{"username": "teacher1", "course_shortname": "CURSO1", "role": "editingteacher"}]
    await service.enrol_users(enrolments)

    last_call_params = service._client.get.call_args[1]["params"]
    assert last_call_params["wsfunction"] == "enrol_manual_enrol_users"
    assert last_call_params["enrolments[0][userid]"] == 10
    assert last_call_params["enrolments[0][courseid]"] == 200
    assert last_call_params["enrolments[0][roleid]"] == 3  # editingteacher


# ---------------------------------------------------------------------------
# Delegación al adapter (self enrolment)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_enable_self_enrolment_delegates_to_adapter(moodle_service):
    """enable_self_enrolment debe delegar en el adapter."""
    service, mock_adapter = moodle_service
    mock_adapter.enable_self_enrolment.return_value = {"id": 99}

    result = await service.enable_self_enrolment(500)
    assert result["id"] == 99
    mock_adapter.enable_self_enrolment.assert_awaited_once_with(500, service._request)


@pytest.mark.asyncio
async def test_get_courses_delegates_to_adapter(moodle_service):
    """get_courses debe delegar en el adapter."""
    service, mock_adapter = moodle_service
    mock_adapter.get_courses.return_value = [{"id": 1, "shortname": "T1"}]

    result = await service.get_courses(shortname="T1")
    assert result[0]["shortname"] == "T1"
    mock_adapter.get_courses.assert_awaited_once_with("T1", service._request)


@pytest.mark.asyncio
async def test_get_courses_bare_delegates_to_adapter(moodle_service):
    """get_courses sin argumentos debe delegar en el adapter."""
    service, mock_adapter = moodle_service
    mock_adapter.get_courses.return_value = []

    result = await service.get_courses()
    assert result == []
    mock_adapter.get_courses.assert_awaited_once_with(None, service._request)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limiter_called(moodle_service):
    """Cada llamada a _request debe pasar por el rate limiter."""
    service, _ = moodle_service
    mock_limiter = AsyncMock()
    service._rate_limiter = mock_limiter
    fake_response = MagicMock()
    fake_response.json.return_value = {}
    fake_response.raise_for_status.return_value = None
    service._client.get.return_value = fake_response

    await service._request("core_webservice_get_site_info", {})
    mock_limiter.acquire.assert_called_once()