from app.core.config import settings
from app.services.moodle_operations import MoodleService


def get_moodle_service(modalidad: str) -> MoodleService:
    config = settings.get_moodle_config(modalidad)
    return MoodleService(
        token=config["token"],
        base_url=config["url"],
        version=config["version"],
    )
