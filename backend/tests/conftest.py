"""
Fixtures compartidos para los tests de SIAUGESMAT.

Proporciona:
- Cliente HTTP de prueba (FastAPI TestClient) con base de datos en memoria.
- Sesión de base de datos SQLite para verificar resultados.
- Cabeceras de autenticación con JWT de prueba.
- Mock del servicio de Moodle para aislar las pruebas de la API externa.
"""

import os
import tempfile

import pytest

# Cargar variables de entorno del .env SOLO cuando se solicita explícitamente
# (SIAUGESMAT_TESTS_USE_DOTENV=1). Por defecto los tests corren contra una
# SQLite temporal, evitando que drop_all/create_all de cada test toque una
# base de datos real. En CI no existe backend/.env, así que también se usa
# SQLite, manteniendo consistencia con el entorno local.
if os.environ.get("SIAUGESMAT_TESTS_USE_DOTENV") == "1":
    try:
        from dotenv import load_dotenv

        _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(_env_path, override=True)
    except ImportError:
        pass


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: test de integración real contra Moodle")

    # Usar base de datos basada en archivo para que todas las conexiones / hilos
    # compartan los mismos datos. El path se genera una vez al importar el módulo.
    # Solo se usa SQLite si no hay DATABASE_URL configurada (tests de integración
    # usan PostgreSQL real desde .env).


_is_sqlite = "sqlite" in os.environ.get("DATABASE_URL", "sqlite")
_test_db_path = os.path.join(tempfile.gettempdir(), f"test_siaugesmat_{os.urandom(4).hex()}.db")
if _is_sqlite:
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path}")
os.environ.setdefault("JWT_SECRET_KEY", "clave-secreta-de-prueba-suficientemente-larga")
os.environ.setdefault("MOODLE_ADMIN_TOKEN", "token-de-prueba")
# Defaults para validar_critico() del lifespan (CI/entornos sin .env).
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/15")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8000")

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import obtener_db, obtener_limitador_login
from app.core.seguridad import crear_token_acceso
from app.db.base import Base
from app.db.modelos import (  # noqa: F401  # asegura que los modelos se registren
    Ejecucion,
    RegistroError,
)
from app.main import app

# ---------------------------------------------------------------------------
# Configuración de la base de datos basada en archivo para pruebas
# ---------------------------------------------------------------------------
if _is_sqlite:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
else:
    engine = create_engine(os.environ["DATABASE_URL"])
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear tablas al importar. Luego cada test_db las dropea y recrea para
# aislar los datos entre tests, compartiendo siempre el mismo archivo SQLite
# con la aplicación (que corre en otro hilo via TestClient).
if _is_sqlite:
    Base.metadata.create_all(bind=engine)

    # ---------------------------------------------------------------------------
    # Fixture: sesión de base de datos de prueba con aislamiento entre tests
    # ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def test_db():
    """Proporciona una sesión y limpia todas las tablas al finalizar."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # ---------------------------------------------------------------------------
        # Fixture: cliente HTTP de FastAPI con la dependencia de BD sobreescrita
        # ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def client(test_db):
    """Cliente de pruebas que inyecta la sesión en memoria en los endpoints."""

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    async def override_limitador_login():
        # Limitador falso: nunca bloquea y no requiere Redis.
        limitador = AsyncMock()
        limitador.esta_bloqueado.return_value = False
        limitador.registrar_exito.return_value = None
        return limitador

    app.dependency_overrides[obtener_db] = override_get_db
    app.dependency_overrides[obtener_limitador_login] = override_limitador_login
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()

    # ---------------------------------------------------------------------------
    # Fixture: cabeceras de autenticación (usuario de pruebas)
    # ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def encabezados_auth():
    """Genera un token JWT válido para 'testuser' con ID=1."""
    token = crear_token_acceso(data={"sub": "1", "username": "testuser", "modalidad": "DISTANCIA"})
    return {"Authorization": f"Bearer {token}"}

    # ---------------------------------------------------------------------------
    # Fixture: mock genérico de MoodleService (AsyncMock)
    # ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def mock_moodle_service():
    """
    Crea un AsyncMock que reemplaza a MoodleService en todas sus llamadas.
    Se puede personalizar en cada test (ej. mock_moodle_service.create_courses.return_value = [...]).
    """
    with patch("app.services.operaciones_moodle.ServicioMoodle", autospec=True) as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        # Configurar métodos comunes con valores por defecto que indiquen éxito
        mock_instance.crear_categorias.return_value = []
        mock_instance.obtener_categorias.return_value = []
        mock_instance.crear_cursos.return_value = []
        mock_instance.obtener_cursos.return_value = []
        mock_instance.actualizar_cursos.return_value = None
        mock_instance.eliminar_cursos.return_value = None
        mock_instance.habilitar_automatriculacion.return_value = {}
        mock_instance.crear_usuarios.return_value = []
        mock_instance.eliminar_usuarios.return_value = None
        mock_instance.obtener_usuarios.return_value = []
        mock_instance.matricular_usuarios.return_value = None
        mock_instance.get_template_course.return_value = None
        yield mock_instance
