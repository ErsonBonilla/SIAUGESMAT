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

# Cargar variables de entorno del .env para tests de integración real
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(_env_path)
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
os.environ.setdefault("JWT_SECRET_KEY", "clave-secreta-de-prueba")
os.environ.setdefault("MOODLE_ADMIN_TOKEN", "token-de-prueba")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

from app.db.base import Base
from app.db.models import Execution, ErrorLog   # noqa: F401  # asegura que los modelos se registren
from app.main import app
from app.core.security import create_access_token
from app.core.dependencies import get_db
from app.services.moodle import MoodleService

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

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixture: cabeceras de autenticación (usuario de pruebas)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def auth_headers():
    """Genera un token JWT válido para 'testuser' con ID=1."""
    token = create_access_token(data={"sub": "1", "username": "testuser", "modalidad": "DISTANCIA"})
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
    with patch("app.services.moodle.MoodleService", autospec=True) as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        # Configurar métodos comunes con valores por defecto que indiquen éxito
        mock_instance.create_categories.return_value = []
        mock_instance.get_categories.return_value = []
        mock_instance.create_courses.return_value = []
        mock_instance.get_courses.return_value = []
        mock_instance.update_courses.return_value = None
        mock_instance.delete_courses.return_value = None
        mock_instance.enable_self_enrolment.return_value = {}
        mock_instance.create_users.return_value = []
        mock_instance.delete_users.return_value = None
        mock_instance.get_users.return_value = []
        mock_instance.enrol_users.return_value = None
        mock_instance.get_template_course.return_value = None
        yield mock_instance