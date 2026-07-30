"""
Configuración central de la aplicación SIAUGESMAT.

Utiliza pydantic-settings para cargar variables de entorno desde un archivo .env
y proporcionar valores tipados y validados a todos los módulos.
"""

import os
from pathlib import Path
from typing import Dict, Optional

from pydantic import model_validator
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
    # URL, token y versión base (fallback si no existe por modalidad)
    MOODLE_URL: str = ""
    MOODLE_TOKEN: str = ""
    MOODLE_ADMIN_TOKEN: str = ""  # alias legacy
    MOODLE_VERSION: str = "3.9"

    # Permitir login en modalidad PRESENCIAL (deshabilitado por contrato)
    ALLOW_PRESENCIAL: bool = False

    # Configuración por modalidad (opcional, sobreescribe la base)
    MOODLE_URL__PRESENCIAL: Optional[str] = None
    MOODLE_TOKEN__PRESENCIAL: Optional[str] = None
    MOODLE_VERSION__PRESENCIAL: Optional[str] = None
    MOODLE_URL__DISTANCIA: Optional[str] = None
    MOODLE_TOKEN__DISTANCIA: Optional[str] = None
    MOODLE_VERSION__DISTANCIA: Optional[str] = None

    # Rate limiting para la API de Moodle
    MOODLE_MAX_REQUESTS_PER_SECOND: int = 5         # llamadas por segundo
    MOODLE_BURST_SIZE: int = 10                     # capacidad máxima del bucket

    # Tiempo máximo de espera por solicitud (segundos)
    # Operaciones pesadas (import_course) usan 120s por separado.
    MOODLE_REQUEST_TIMEOUT: float = 60.0

    # Reintentos automáticos ante fallos de red
    MOODLE_MAX_RETRIES: int = 3

    # Tamaño de lote para consultas masivas a Moodle
    MOODLE_QUERY_BATCH_SIZE: int = 5

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
    # Institucional
    # ------------------------------------------------------------------
    INSTITUTIONAL_EMAIL_DOMAIN: str = "@ut.edu.co"
    ROOT_CATEGORY_NAME: str = "IDEAD"
    DEFAULT_COURSE_FORMAT: str = "onetopic"

    # ------------------------------------------------------------------
    # Comparación de cursos (FASE 2)
    # ------------------------------------------------------------------
    COURSE_MAX_AGE_SECONDS: int = 18 * 30 * 24 * 3600       # 18 meses
    COURSE_DISAPPEARED_AGE_SECONDS: int = 6 * 30 * 24 * 3600  # 6 meses

    # ------------------------------------------------------------------
    # Archivos subidos
    # ------------------------------------------------------------------
    UPLOAD_DIR: str = str(Path(__file__).resolve().parent.parent.parent / "uploads")

    # ------------------------------------------------------------------
    # Reportes
    # ------------------------------------------------------------------
    REPORT_DIR: str = str(Path(__file__).resolve().parent.parent.parent / "reports")

    # Tamaño máximo de archivo en megabytes
    MAX_UPLOAD_SIZE_MB: int = 50

    # ------------------------------------------------------------------
    # Trabajos ETL
    # ------------------------------------------------------------------
    # Tiempo máximo de ejecución de un trabajo (segundos)
    JOB_TIMEOUT: int = 28800                         # 8 horas

    # Máximo de cursos a eliminar automáticamente. Si el plan supera
    # este número, la ejecución se detiene y requiere confirmación manual.
    MAX_AUTO_DELETE_COURSES: int = 500

    # Tiempo de espera para considerar un item como "stuck" (minutos)
    STUCK_ITEM_TIMEOUT_MINUTES: int = 30

    # Tiempo de espera para considerar una ejecución como "stuck" (segundos)
    STUCK_EXECUTION_TIMEOUT: int = 21600                   # 6 horas

    # Días de antigüedad para limpieza automática de lotes
    DEFAULT_BATCH_CLEANUP_DAYS: int = 30

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
        extra="ignore",
    )

    def get_moodle_config(self, modalidad: str) -> Dict[str, str]:
        suffix = modalidad.strip().upper()

        def _get(*keys: str) -> str:
            for base_key in keys:
                modal_key = f"{base_key}__{suffix}"
                val = getattr(self, modal_key, None) or getattr(self, base_key, None)
                if val:
                    return val
            raise ValueError(
                f"Ninguna variable configurada para la modalidad '{modalidad}'. "
                f"Buscó: {[f'{k}__{suffix}' for k in keys]}. "
                f"Defínela como variable de entorno."
            )

        return {
            "url": _get("MOODLE_URL"),
            "token": _get("MOODLE_TOKEN", "MOODLE_ADMIN_TOKEN"),
            "version": _get("MOODLE_VERSION"),
        }

    def validate_critical(self):
        errors = []
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL no está configurada")
        if not self.REDIS_URL:
            errors.append("REDIS_URL no está configurada")
        if not self.JWT_SECRET_KEY:
            errors.append("JWT_SECRET_KEY no está configurada")
        if errors:
            raise ValueError(
                "Errores de configuración crítica:\n  - " + "\n  - ".join(errors)
            )


# Instancia única de configuración para toda la aplicación
settings = Settings()