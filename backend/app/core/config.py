"""
Configuración central de la aplicación SIAUGESMAT.

Utiliza pydantic-settings para cargar variables de entorno desde un archivo .env
y proporcionar valores tipados y validados a todos los módulos.
"""

import os
from pathlib import Path
from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de la aplicación.

    Todas las variables pueden sobrescribirse mediante un archivo .env o directamente
    como variables de entorno del sistema.
    """

    # ------------------------------------------------------------------
    # Proyecto
    # ------------------------------------------------------------------
    PROJECT_NAME: str = "SIAUGESMAT"
    PROJECT_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ------------------------------------------------------------------
    # Moodle
    # ------------------------------------------------------------------
    # La URL, token y versión se definen por modalidad como variables
    # de entorno con el formato MOODLE_URL__{MODALIDAD}, MOODLE_TOKEN__{MODALIDAD},
    # MOODLE_VERSION__{MODALIDAD} (ej. MOODLE_URL__PRESENCIAL).

    # Rate limiting para la API de Moodle
    MOODLE_MAX_REQUESTS_PER_SECOND: int = 5         # llamadas por segundo
    MOODLE_BURST_SIZE: int = 10                     # capacidad máxima del bucket

    # Tiempo máximo de espera por solicitud (segundos)
    MOODLE_REQUEST_TIMEOUT: float = 120.0

    # Reintentos automáticos ante fallos de red
    MOODLE_MAX_RETRIES: int = 3

    # ------------------------------------------------------------------
    # Plantilla genérica para cursos sin PORTAFOLIO
    # ------------------------------------------------------------------
    DEFAULT_COURSE_TEMPLATE: str = ""

    # ------------------------------------------------------------------
    # Base de datos PostgreSQL
    # ------------------------------------------------------------------
    DATABASE_URL: str = ""

    # ------------------------------------------------------------------
    # Redis (cola de tareas Celery)
    # ------------------------------------------------------------------
    REDIS_URL: str = ""

    # ------------------------------------------------------------------
    # Archivos subidos
    # ------------------------------------------------------------------
    UPLOAD_DIR: str = os.path.join(os.getcwd(), "uploads")

    # ------------------------------------------------------------------
    # Reportes
    # ------------------------------------------------------------------
    REPORT_DIR: str = os.path.join(os.getcwd(), "reports")

    # Tamaño máximo de archivo en megabytes
    MAX_UPLOAD_SIZE_MB: int = 50

    # ------------------------------------------------------------------
    # Trabajos ETL
    # ------------------------------------------------------------------
    # Tiempo máximo de ejecución de un trabajo (segundos)
    JOB_TIMEOUT: int = 7200                          # 2 horas por defecto

    # ------------------------------------------------------------------
    # Umbrales del semáforo de analítica
    # ------------------------------------------------------------------
    # Tasa de error (porcentaje) para activar el nivel amarillo
    ANALYTICS_ERROR_THRESHOLD_YELLOW: float = 1.0

    # Tasa de error (porcentaje) para activar el nivel rojo
    ANALYTICS_ERROR_THRESHOLD_RED: float = 5.0

    # Duración máxima en segundos para considerar advertencia (amarillo)
    ANALYTICS_MAX_DURATION_YELLOW: float = 3600.0    # 1 hora

    # Duración máxima en segundos para considerar crítico (rojo)
    ANALYTICS_MAX_DURATION_RED: float = 7200.0       # 2 horas

    # ------------------------------------------------------------------
    # Autenticación JWT
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    CORS_ORIGINS: str = ""

    # ------------------------------------------------------------------
    # Configuración del modelo de Pydantic-settings
    # ------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    def get_moodle_config(self, modalidad: str) -> Dict[str, str]:
        """
        Resuelve URL, token y versión de Moodle para una modalidad.

        Busca variables de entorno con el formato:
          MOODLE_URL__{MODALIDAD}
          MOODLE_TOKEN__{MODALIDAD}
          MOODLE_VERSION__{MODALIDAD}

        Raises:
            ValueError: Si alguna variable de entorno no está configurada.
        """
        suffix = modalidad.strip().upper()

        def _get(key: str) -> str:
            val = os.environ.get(key)
            if not val:
                raise ValueError(
                    f"{key} no está configurada en el .env para la modalidad '{modalidad}'. "
                    f"Defínela como variable de entorno."
                )
            return val

        return {
            "url": _get(f"MOODLE_URL__{suffix}"),
            "token": _get(f"MOODLE_TOKEN__{suffix}"),
            "version": _get(f"MOODLE_VERSION__{suffix}"),
        }


# Instancia única de configuración para toda la aplicación
settings = Settings()