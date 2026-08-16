"""
Contrato wire (JSON) entre backend y frontend: claves en inglés.

Estos tests previenen que un futuro renombrado sin ``Field(alias=...)``
rompa el formato JSON que consume el frontend (`frontend/services/api/tipos.ts`).
"""

from datetime import UTC, datetime

from app.schemas.operaciones import ItemOperacionSalida, LoteSalidaLista
from app.schemas.trabajo import EjecucionSalida, ErrorSalida


def _dump(modelo):
    return modelo.model_dump(by_alias=True)


def test_error_salida_serializa_claves_inglesas():
    out = _dump(
        ErrorSalida(
            id=1,
            ejecucion_id=2,
            tipo="error",
            identificador="CAL_0001",
            mensaje="boom",
            creado_en=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert set(out) == {"id", "execution_id", "type", "identifier", "message", "created_at"}


def test_ejecucion_salida_serializa_claves_inglesas():
    out = _dump(
        EjecucionSalida(
            id=1,
            nombre_archivo="carga.xlsx",
            semestre="2026A",
            modo="both",
            estado="completed",
            metricas={"courses_created": 3},
            conteo_errores=0,
            iniciado_en=datetime(2026, 1, 1, tzinfo=UTC),
            completado_en=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
            duracion_segundos=3600.0,
            version_moodle="3.9",
            modalidad="DISTANCIA",
            directorio_reporte="/tmp",
            id_tarea_celery="abc",
            creado_en=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    esperadas = {
        "id",
        "filename",
        "semester",
        "mode",
        "status",
        "metrics",
        "errors_count",
        "current_phase",
        "progress_pct",
        "progress_updated_at",
        "current_step",
        "eta_seconds",
        "started_at",
        "completed_at",
        "duration_seconds",
        "moodle_version",
        "modalidad",
        "report_dir",
        "celery_task_id",
        "created_at",
    }
    assert set(out) == esperadas
    assert out["filename"] == "carga.xlsx"
    assert out["semester"] == "2026A"


def test_ejecucion_acepta_metricas_heterogeneas():
    """Regression: metricas puede contener listas (templates_missing_examples).

    El schema de respuesta no debe 500 al serializar `metrics` con valores no
    numéricos (p. ej. la lista de templates faltantes que guarda el pipeline).
    """
    out = _dump(
        EjecucionSalida(
            id=1,
            nombre_archivo="carga.xlsx",
            semestre="2026B",
            modo="users",
            estado="completed",
            metricas={
                "courses_created": 8,
                "templates_missing": 8,
                "templates_missing_examples": ["PORTAFOLIO_0992_sII_1201065"],
            },
            conteo_errores=0,
            creado_en=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert out["metrics"]["templates_missing_examples"] == ["PORTAFOLIO_0992_sII_1201065"]
    assert out["metrics"]["courses_created"] == 8


def test_item_operacion_serializa_claves_inglesas():
    out = _dump(
        ItemOperacionSalida(
            identificador="CAL_0001", estado="completed", mensaje_error=None, intento=1
        )
    )
    assert set(out) == {"identifier", "status", "error_message", "attempt"}


def test_lote_salida_serializa_claves_inglesas():
    out = _dump(
        LoteSalidaLista(
            id_lote="b-1",
            tipo_entidad="courses",
            accion="create",
            total=10,
            completados=7,
            fallidos=3,
            pausados=0,
            modalidad="DISTANCIA",
            creado_en=datetime(2026, 1, 1, tzinfo=UTC),
            completado_en=None,
        )
    )
    assert set(out) == {
        "batch_id",
        "entity_type",
        "action",
        "total",
        "completed",
        "failed",
        "paused",
        "modalidad",
        "created_at",
        "completed_at",
    }
    assert out["batch_id"] == "b-1"
    assert out["entity_type"] == "courses"
