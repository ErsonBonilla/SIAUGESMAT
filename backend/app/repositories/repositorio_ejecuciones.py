from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.db.modelos import Ejecucion, RegistroError


def obtener_ejecucion(db: Session, ejecucion_id: int) -> Ejecucion | None:
    return db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()


ESTADOS_EJECUCION_ACTIVA = ("queued", "running", "paused", "review_required")


def obtener_ejecucion_activa(
    db: Session, modalidad: str, exclude_id: int | None = None
) -> Ejecucion | None:
    """Devuelve la ejecución en curso (no terminada) de una modalidad.

    Estados considerados activos: queued, running, paused, review_required.
    ``exclude_id`` permite ignorar una ejecución concreta (p. ej. la propia
    al reanudar/confirmar una ejecución).
    """
    query = db.query(Ejecucion).filter(
        Ejecucion.estado.in_(ESTADOS_EJECUCION_ACTIVA),
    )
    if modalidad:
        query = query.filter(Ejecucion.modalidad == modalidad)
    if exclude_id is not None:
        query = query.filter(Ejecucion.id != exclude_id)
    return query.order_by(Ejecucion.creado_en.desc()).first()


def crear_ejecucion(
    db: Session,
    nombre_archivo: str,
    semestre: str,
    modo: str,
    modalidad: str,
    version_moodle: str,
) -> Ejecucion:
    ejecucion = Ejecucion(
        nombre_archivo=nombre_archivo,
        semestre=semestre,
        modo=modo,
        estado="pending",
        version_moodle=version_moodle,
        modalidad=modalidad,
        creado_en=datetime.now(UTC),
    )
    db.add(ejecucion)
    db.commit()
    db.refresh(ejecucion)
    return ejecucion


def marcar_en_cola_atomicamente(
    db: Session, ejecucion_id: int, task_id: str, allowed_statuses: tuple
) -> bool:
    result = (
        db.query(Ejecucion)
        .filter(Ejecucion.id == ejecucion_id, Ejecucion.estado.in_(allowed_statuses))
        .update(
            {
                Ejecucion.estado: "queued",
                Ejecucion.iniciado_en: datetime.now(UTC),
                Ejecucion.id_tarea_celery: task_id,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return result > 0


def actualizar_progreso(
    db: Session, ejecucion_id: int, pct: float, fase: str = None, paso: int = None
) -> None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        if fase is not None:
            ejecucion.fase_actual = fase
        ejecucion.porcentaje_progreso = pct
        ejecucion.progreso_actualizado_en = datetime.now(UTC)
        if paso is not None:
            ejecucion.paso_actual = paso
        db.commit()


def actualizar_heartbeat(db: Session, ejecucion_id: int) -> None:
    """Actualiza solo progreso_actualizado_en sin cambiar porcentaje ni mensaje."""
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        ejecucion.progreso_actualizado_en = datetime.now(UTC)
        db.commit()


def marcar_en_ejecucion(db: Session, ejecucion_id: int) -> Ejecucion | None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        ejecucion.estado = "running"
        ejecucion.iniciado_en = datetime.now(UTC)
        ejecucion.porcentaje_progreso = 0
        db.commit()
    return ejecucion


def marcar_completado(
    db: Session,
    ejecucion_id: int,
    metricas: dict,
    conteo_errores: int,
    duracion_segundos: float,
) -> Ejecucion | None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        ejecucion.estado = "completed"
        ejecucion.metricas = metricas
        ejecucion.conteo_errores = conteo_errores
        ejecucion.completado_en = datetime.now(UTC)
        ejecucion.duracion_segundos = round(duracion_segundos, 2)
        ejecucion.fase_actual = "Procesamiento completado"
        ejecucion.porcentaje_progreso = 100
        db.commit()
    return ejecucion


def marcar_fallido(db: Session, ejecucion_id: int, duracion_segundos: float) -> Ejecucion | None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        ejecucion.estado = "failed"
        ejecucion.completado_en = datetime.now(UTC)
        ejecucion.duracion_segundos = round(duracion_segundos, 2)
        db.commit()
    return ejecucion


def eliminar_ejecucion(db: Session, ejecucion_id: int) -> None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        db.delete(ejecucion)
        db.commit()


def listar_ejecuciones(
    db: Session,
    semestre: str = None,
    estado: str = None,
    modo: str = None,
    version_moodle: str = None,
    modalidad: str = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[Ejecucion]]:
    query = db.query(Ejecucion)
    if semestre:
        query = query.filter(Ejecucion.semestre == semestre)
    if estado:
        query = query.filter(Ejecucion.estado == estado)
    if modo:
        query = query.filter(Ejecucion.modo == modo)
    if version_moodle:
        query = query.filter(Ejecucion.version_moodle == version_moodle)
    if modalidad:
        query = query.filter(Ejecucion.modalidad == modalidad.upper())
    total = query.count()
    ejecuciones = query.order_by(Ejecucion.creado_en.desc()).offset(offset).limit(limit).all()
    return total, ejecuciones


def obtener_errores_ejecucion(
    db: Session, ejecucion_id: int, limit: int, offset: int
) -> list[RegistroError]:
    return (
        db.query(RegistroError)
        .filter(RegistroError.ejecucion_id == ejecucion_id)
        .order_by(RegistroError.creado_en.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def establecer_directorio_reportes(db: Session, ejecucion_id: int, directorio_reporte: str) -> None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        ejecucion.directorio_reporte = directorio_reporte
        db.commit()


def es_re_subida(db: Session, semestre: str, modalidad: str, exclude_id: int) -> bool:
    return (
        db.query(Ejecucion)
        .filter(
            Ejecucion.semestre == semestre,
            Ejecucion.modalidad == modalidad,
            Ejecucion.estado == "completed",
            Ejecucion.id != exclude_id,
        )
        .first()
        is not None
    )


def eliminar_ejecuciones_pendientes_antiguas(db: Session, hours: int = 24) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    old = (
        db.query(Ejecucion)
        .filter(
            Ejecucion.estado == "pending",
            Ejecucion.creado_en < cutoff,
        )
        .all()
    )
    if not old:
        return 0
    for ex in old:
        db.delete(ex)
    db.commit()
    return len(old)


def guardar_checkpoint(db: Session, ejecucion_id: int, fase: str, data: dict) -> None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        if ejecucion.checkpoint_fase is None:
            ejecucion.checkpoint_fase = {}
        ejecucion.checkpoint_fase[fase] = data
        flag_modified(ejecucion, "checkpoint_fase")
        db.commit()


def obtener_checkpoint(db: Session, ejecucion_id: int) -> dict | None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if not ejecucion or not ejecucion.checkpoint_fase:
        return None
    return dict(ejecucion.checkpoint_fase)


def marcar_chord_activo(db: Session, ejecucion_id: int, minutes: int = None) -> None:
    """Marca un chord de fase como activo hasta una fecha de expiración.

    El sweeper ``recover_stuck_phase`` usa esta marca para relanzar una fase
    cuyo chord quedó huérfano (worker caído, callback nunca ejecutado).
    """
    minutes = settings.CHORD_ACTIVE_MINUTES if minutes is None else minutes
    expires = datetime.now(UTC) + timedelta(minutes=minutes)
    guardar_checkpoint(db, ejecucion_id, "chord_active", expires.isoformat())


def limpiar_chord_activo(db: Session, ejecucion_id: int) -> None:
    """Limpia la marca de chord activo (al iniciar el callback de la fase)."""
    guardar_checkpoint(db, ejecucion_id, "chord_active", None)


def limpiar_checkpoint(db: Session, ejecucion_id: int) -> None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        ejecucion.checkpoint_fase = None
        flag_modified(ejecucion, "checkpoint_fase")
        db.commit()


def pausar_ejecucion(db: Session, ejecucion_id: int) -> tuple[bool, str]:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if not ejecucion or ejecucion.estado != "running":
        return False, ""
    task_id = ejecucion.id_tarea_celery or ""
    ejecucion.estado = "paused"
    if " (pausado)" not in (ejecucion.fase_actual or ""):
        ejecucion.fase_actual = f"{ejecucion.fase_actual or ''} (pausado)"
    db.commit()
    return True, task_id


def incrementar_metrica(
    db: Session, ejecucion_id: int, nombre_metrica: str, delta: int = 1
) -> None:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        metricas = ejecucion.metricas or {}
        metricas[nombre_metrica] = metricas.get(nombre_metrica, 0) + delta
        ejecucion.metricas = metricas
        flag_modified(ejecucion, "metricas")
        db.flush()


def sincronizar_conteo_errores(db: Session, ejecucion_id: int) -> None:
    """Sincroniza la columna ``conteo_errores`` con el total de errores en vivo.

    Antes solo se escribía al completar la ejecución; durante ``running`` el
    semáforo y las listas mostraban 0 aunque ya hubiera errores.
    """
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if ejecucion:
        metricas = ejecucion.metricas or {}
        ejecucion.conteo_errores = metricas.get("total_errors", 0)
        db.flush()


def debe_pausarse(db: Session, ejecucion_id: int) -> bool:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    return ejecucion is not None and ejecucion.estado == "paused"


def cancelar_ejecucion(db: Session, ejecucion_id: int) -> tuple[bool, str]:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    if not ejecucion or ejecucion.estado not in ("running", "paused", "queued"):
        return False, ""
    task_id = ejecucion.id_tarea_celery or ""
    ejecucion.estado = "cancelled"
    ejecucion.fase_actual = f"{ejecucion.fase_actual or ''} (cancelado)"
    ejecucion.completado_en = datetime.now(UTC)
    ejecucion.duracion_segundos = (
        round((datetime.now(UTC) - ejecucion.iniciado_en).total_seconds())
        if ejecucion.iniciado_en
        else 0
    )
    db.commit()
    return True, task_id


def debe_cancelarse(db: Session, ejecucion_id: int) -> bool:
    ejecucion = db.query(Ejecucion).filter(Ejecucion.id == ejecucion_id).first()
    return ejecucion is not None and ejecucion.estado == "cancelled"
