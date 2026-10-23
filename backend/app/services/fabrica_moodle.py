from app.core.config import settings
from app.services.operaciones_moodle import ServicioMoodle


def obtener_servicio_moodle(modalidad: str) -> ServicioMoodle:
    config = settings.obtener_config_moodle(modalidad)
    return ServicioMoodle(
        token=config["token"],
        base_url=config["url"],
        version=config["version"],
    )
