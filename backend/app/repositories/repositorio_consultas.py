from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.modelos import ResultadoConsulta


def obtener_consulta(db: Session, id_tarea: str) -> ResultadoConsulta | None:
    return db.query(ResultadoConsulta).filter_by(id_tarea=id_tarea).first()


def crear_consulta(
    db: Session, id_tarea: str, entidad: str, parametros: dict, modalidad: str
) -> ResultadoConsulta:
    qr = ResultadoConsulta(
        id_tarea=id_tarea,
        entidad=entidad,
        parametros=parametros,
        estado="pending",
        modalidad=modalidad,
    )
    db.add(qr)
    db.commit()
    return qr


def marcar_consulta_en_ejecucion(db: Session, id_tarea: str) -> ResultadoConsulta | None:
    qr = db.query(ResultadoConsulta).filter_by(id_tarea=id_tarea).first()
    if qr:
        qr.estado = "running"
        qr.mensaje_error = None
        qr.resultado_json = None
        qr.completado_en = None
        db.commit()
    return qr


def marcar_consulta_completada(
    db: Session, id_tarea: str, resultado_json, conteo_total: int
) -> ResultadoConsulta | None:
    qr = db.query(ResultadoConsulta).filter_by(id_tarea=id_tarea).first()
    if qr:
        qr.resultado_json = resultado_json
        qr.conteo_total = conteo_total
        qr.estado = "completed"
        qr.completado_en = datetime.now(UTC)
        db.commit()
    return qr


def marcar_consulta_fallida(
    db: Session, id_tarea: str, mensaje_error: str
) -> ResultadoConsulta | None:
    qr = db.query(ResultadoConsulta).filter_by(id_tarea=id_tarea).first()
    if qr:
        qr.estado = "failed"
        qr.mensaje_error = mensaje_error[:500]
        qr.completado_en = datetime.now(UTC)
        db.commit()
    return qr


def eliminar_consultas_antiguas(db: Session, days: int) -> int:
    if days < 1:
        raise ValueError("El parámetro 'days' debe ser al menos 1.")
    cutoff = datetime.now(UTC) - timedelta(days=days)
    deleted = (
        db.query(ResultadoConsulta)
        .filter(ResultadoConsulta.creado_en < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def obtener_estado_observatorio(
    db: Session, modalidad: str
) -> tuple[ResultadoConsulta | None, ResultadoConsulta | None]:
    """Devuelve (ultima_completada, activa_en_curso) para la entidad 'observatorio'."""
    ultima_completada = (
        db.query(ResultadoConsulta)
        .filter(
            ResultadoConsulta.entidad == "observatorio",
            ResultadoConsulta.modalidad == modalidad,
            ResultadoConsulta.estado == "completed",
        )
        .order_by(ResultadoConsulta.completado_en.desc(), ResultadoConsulta.id.desc())
        .first()
    )
    cutoff_activa = datetime.now(UTC) - timedelta(minutes=20)
    activa_en_curso = (
        db.query(ResultadoConsulta)
        .filter(
            ResultadoConsulta.entidad == "observatorio",
            ResultadoConsulta.modalidad == modalidad,
            ResultadoConsulta.estado.in_(("pending", "running")),
            ResultadoConsulta.creado_en >= cutoff_activa,
        )
        .order_by(ResultadoConsulta.creado_en.desc(), ResultadoConsulta.id.desc())
        .first()
    )
    return ultima_completada, activa_en_curso
