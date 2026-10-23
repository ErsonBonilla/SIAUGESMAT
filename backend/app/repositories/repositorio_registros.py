from sqlalchemy.orm import Session

from app.db.modelos import RegistroEjecucion, RegistroError


def guardar_log(
    db: Session,
    ejecucion_id: int,
    fase: str,
    accion: str,
    identificador: str = None,
    detalle: dict = None,
) -> None:
    log = RegistroEjecucion(
        ejecucion_id=ejecucion_id,
        fase=fase,
        accion=accion,
        identificador=identificador,
        detalle=detalle or {},
    )
    db.add(log)
    db.flush()


def guardar_error(
    db: Session,
    ejecucion_id: int,
    tipo: str,
    identificador: str = None,
    mensaje: str = None,
) -> None:
    error = RegistroError(
        ejecucion_id=ejecucion_id,
        tipo=tipo,
        identificador=identificador,
        mensaje=mensaje,
    )
    db.add(error)
    db.flush()


def obtener_logs_ejecucion(
    db: Session, ejecucion_id: int, limit: int = 100, offset: int = 0
) -> list[RegistroEjecucion]:
    return (
        db.query(RegistroEjecucion)
        .filter(RegistroEjecucion.ejecucion_id == ejecucion_id)
        .order_by(RegistroEjecucion.creado_en.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
