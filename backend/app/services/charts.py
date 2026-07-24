import logging
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

os.environ.setdefault("KALEIDO_CHROMIUM_PATH", os.environ.get("CHROME_PATH", "/usr/bin/chromium"))
os.environ.setdefault("KALEIDO_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-dev-shm-usage --disable-setuid-sandbox --no-zygote")

import plotly.graph_objects as go

from app.db.models import Execution, ExecutionLog
from app.services.parsers.patterns import SHORTNAME_PATTERN, get_semestre

logger = logging.getLogger(__name__)

PALETTE_LIGHT = {
    "rojo": "#ED3237",
    "verde": "#00A859",
    "blanco": "#FFFFFF",
    "negro": "#1A1A1A",
    "grid": "#E0E0E0",
}

PALETTE_DARK = {
    "rojo": "#F87171",
    "verde": "#34D399",
    "blanco": "#1e1e2e",
    "negro": "#cdd6f4",
    "grid": "#45475a",
}

PALETTE_CATEGORICAL_LIGHT = [
    "#ED3237", "#00A859", "#1A1A1A", "#E63946",
    "#2D6A4F", "#404040", "#FF6B6B", "#40916C",
]

PALETTE_CATEGORICAL_DARK = [
    "#F87171", "#34D399", "#cdd6f4", "#FCA5A5",
    "#6EE7B7", "#a6adc8", "#FCA5A5", "#A7F3D0",
]


def _get_palette(theme: str = "light") -> dict:
    return PALETTE_DARK if theme == "dark" else PALETTE_LIGHT


def _get_categorical(theme: str = "light") -> list:
    return PALETTE_CATEGORICAL_DARK if theme == "dark" else PALETTE_CATEGORICAL_LIGHT


def _semestre_from_shortname(shortname: str) -> Optional[str]:
    m = SHORTNAME_PATTERN.match(shortname)
    return get_semestre(m) if m else None


def _cat_prefix_from_shortname(shortname: str) -> Optional[str]:
    m = SHORTNAME_PATTERN.match(shortname)
    return m.group("cat_prefix") if m else None


def _default_fig(title: str, theme: str = "light") -> go.Figure:
    palette = _get_palette(theme)
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=palette["negro"])),
        font=dict(color=palette["negro"]),
        plot_bgcolor=palette["blanco"],
        paper_bgcolor=palette["blanco"],
        margin=dict(l=60, r=40, t=60, b=60),
        legend=dict(font=dict(color=palette["negro"])),
    )
    fig.update_xaxes(gridcolor=palette["grid"], tickfont=dict(color=palette["negro"]))
    fig.update_yaxes(gridcolor=palette["grid"], tickfont=dict(color=palette["negro"]))
    return fig


class ChartService:

    CHART_NAMES = {
        "resumen_ejecutivo": "1_resumen_ejecutivo",
        "tasa_exito": "2_tasa_exito",
        "top_programas": "3_top_programas",
        "distribucion_usuarios": "4_distribucion_usuarios",
        "top_incidencias": "5_top_incidencias",
    }

    @classmethod
    def generate_all(cls, execution: Execution, logs: List[ExecutionLog], report_dir: str):
        for key, prefix in cls.CHART_NAMES.items():
            method = getattr(cls, key, None)
            if not method:
                continue
            try:
                fig = method(execution, logs, theme="light")
                if fig is None:
                    continue
                png_path = os.path.join(report_dir, f"{prefix}.png")
                html_path = os.path.join(report_dir, f"{prefix}.html")
                fig.write_html(html_path, include_plotlyjs="cdn")
                try:
                    fig.write_image(png_path, width=800, height=450, scale=2)
                except Exception:
                    logger.warning(f"Gráfico {prefix}: solo HTML (PNG requiere Chrome)")
                logger.info(f"Gráfico generado: {prefix}")
            except Exception as e:
                logger.exception(f"Error generando gráfico {key}: {e}")

    @classmethod
    def _figure_to_dict(cls, fig: go.Figure) -> Dict[str, Any]:
        return {
            "traces": [t.to_plotly_json() for t in fig.data],
            "layout": fig.layout.to_plotly_json(),
        }

    # ------------------------------------------------------------------
    # 1. Resumen ejecutivo — 4 KPIs en barras horizontales
    # ------------------------------------------------------------------
    @classmethod
    def resumen_ejecutivo(cls, execution: Execution, logs: List[ExecutionLog], theme: str = "light") -> go.Figure:
        palette = _get_palette(theme)
        m = execution.metrics or {}
        labels = ["Cursos creados", "Usuarios nuevos", "Matrículas exitosas", "Errores totales"]
        values = [
            m.get("courses_created", 0),
            m.get("users_created", 0),
            m.get("enrolments", 0),
            m.get("total_errors", 0),
        ]
        colors = [palette["verde"], palette["verde"], palette["verde"], palette["rojo"]]
        fig = _default_fig("", theme)
        fig.add_trace(go.Bar(
            y=labels, x=values, orientation="h",
            marker_color=colors, text=values, textposition="outside",
            textfont=dict(color=palette["negro"]),
        ))
        fig.update_layout(
            title=dict(text="Resumen ejecutivo", font=dict(size=16, color=palette["negro"])),
            xaxis=dict(title="Cantidad", dtick=1, gridcolor=palette["grid"]),
            yaxis=dict(gridcolor=palette["grid"]),
            showlegend=False, margin=dict(l=150, r=80, t=50, b=30),
        )
        return fig

    @classmethod
    def resumen_ejecutivo_json(cls, execution, logs, theme="light"):
        return cls._figure_to_dict(cls.resumen_ejecutivo(execution, logs, theme))

    # ------------------------------------------------------------------
    # 2. Tasa de éxito de matrícula — donut con % grande al centro
    # ------------------------------------------------------------------
    @classmethod
    def tasa_exito(cls, execution: Execution, logs: List[ExecutionLog], theme: str = "light") -> go.Figure:
        palette = _get_palette(theme)
        m = execution.metrics or {}
        ok = m.get("enrolments", 0)
        fail = m.get("enrolment_errors", 0)
        total = ok + fail
        rate = round(ok / total * 100, 1) if total > 0 else 0
        color = palette["verde"] if rate >= 95 else ("#F59E0B" if rate >= 85 else palette["rojo"])

        fig = _default_fig("", theme)
        fig.add_trace(go.Pie(
            labels=["Exitosas", "Fallidas"], values=[ok, fail],
            hole=0.7, marker=dict(colors=[color, "#E5E7EB"]),
            textinfo="none", sort=False,
        ))
        fig.add_annotation(
            text=f"<b>{rate}%</b>", font=dict(size=36, color=color), showarrow=False,
            x=0.5, y=0.5, xref="paper", yref="paper",
        )
        fig.update_layout(
            title=dict(text="Tasa de éxito de matrícula", font=dict(size=16, color=palette["negro"])),
            showlegend=True, legend=dict(orientation="h", y=-0.1, font=dict(color=palette["negro"])),
            margin=dict(l=30, r=30, t=50, b=50),
        )
        return fig

    @classmethod
    def tasa_exito_json(cls, execution, logs, theme="light"):
        return cls._figure_to_dict(cls.tasa_exito(execution, logs, theme))

    # ------------------------------------------------------------------
    # 3. Top 10 programas — barras horizontales por cantidad de cursos
    # ------------------------------------------------------------------
    @classmethod
    def top_programas(cls, execution: Execution, logs: List[ExecutionLog], theme: str = "light") -> go.Figure:
        palette = _get_palette(theme)
        counts: Dict[str, int] = defaultdict(int)
        for log_entry in logs:
            sn = log_entry.identifier or ""
            prefix = _cat_prefix_from_shortname(sn)
            if prefix and log_entry.action in (
                "course_created", "course_created_with_template", "course_recreated",
            ):
                counts[prefix] += 1
        program_names = {"IDE": "IDEAD", "URA": "Urabá", "FAC": "Facultad"}
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [program_names.get(k, k) for k, _ in sorted_items]
        values = [v for _, v in sorted_items]
        fig = _default_fig("", theme)
        fig.add_trace(go.Bar(
            y=labels, x=values, orientation="h",
            marker_color=palette["verde"], text=values, textposition="outside",
            textfont=dict(color=palette["negro"]),
        ))
        fig.update_layout(
            title=dict(text="Top programas", font=dict(size=16, color=palette["negro"])),
            xaxis=dict(title="Cursos", dtick=1, gridcolor=palette["grid"]),
            yaxis=dict(gridcolor=palette["grid"]),
            showlegend=False, margin=dict(l=120, r=60, t=50, b=30),
        )
        fig.update_yaxes(autorange="reversed")
        return fig

    @classmethod
    def top_programas_json(cls, execution, logs, theme="light"):
        return cls._figure_to_dict(cls.top_programas(execution, logs, theme))

    # ------------------------------------------------------------------
    # 4. Distribución de usuarios — donut nuevos vs existentes
    # ------------------------------------------------------------------
    @classmethod
    def distribucion_usuarios(cls, execution: Execution, logs: List[ExecutionLog], theme: str = "light") -> go.Figure:
        palette = _get_palette(theme)
        nuevos = sum(1 for l in logs if l.action == "user_created_createpassword")
        resueltos = sum(1 for l in logs if l.action == "user_resolved")
        total = nuevos + resueltos
        if total == 0:
            fig = _default_fig("", theme)
            fig.update_layout(title=dict(text="Usuarios", font=dict(size=16, color=palette["negro"])))
            fig.add_annotation(text="Sin datos", showarrow=False, font=dict(color=palette["negro"]))
            return fig
        fig = _default_fig("", theme)
        pct_nuevos = round(nuevos / total * 100)
        fig.add_trace(go.Pie(
            labels=["Nuevos", "Existentes"], values=[nuevos, resueltos],
            hole=0.6, marker=dict(colors=[palette["verde"], palette["negro"]]),
            textinfo="label+percent", sort=False,
        ))
        fig.add_annotation(
            text=f"<b>{pct_nuevos}%</b><br><span style='font-size:12px'>nuevos</span>",
            font=dict(size=28, color=palette["verde"]), showarrow=False,
            x=0.5, y=0.5, xref="paper", yref="paper",
        )
        fig.update_layout(
            title=dict(text="Distribución de usuarios", font=dict(size=16, color=palette["negro"])),
            showlegend=False, margin=dict(l=30, r=30, t=50, b=30),
        )
        return fig

    @classmethod
    def distribucion_usuarios_json(cls, execution, logs, theme="light"):
        return cls._figure_to_dict(cls.distribucion_usuarios(execution, logs, theme))

    # ------------------------------------------------------------------
    # 5. Top 5 incidencias — barras horizontales por frecuencia
    # ------------------------------------------------------------------
    @classmethod
    def top_incidencias(cls, execution: Execution, logs: List[ExecutionLog], theme: str = "light") -> go.Figure:
        palette = _get_palette(theme)
        incidencia_labels = {
            "enrolment_failed": "Matrícula fallida",
            "alert_disappeared_recent": "Curso desaparecido reciente",
            "alert_teacher_change_recent": "Cambio de profesor reciente",
            "duplicate_email": "Correo duplicado",
            "template_not_found": "Plantilla no encontrada",
        }
        counts: Dict[str, int] = defaultdict(int)
        for log_entry in logs:
            label = incidencia_labels.get(log_entry.action)
            if label:
                counts[label] += 1
        if not counts:
            fig = _default_fig("", theme)
            fig.update_layout(title=dict(text="Incidencias", font=dict(size=16, color=palette["negro"])))
            fig.add_annotation(text="Sin incidencias ✓", showarrow=False, font=dict(color=palette["verde"], size=18))
            return fig
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
        labels = [k for k, _ in sorted_items]
        values = [v for _, v in sorted_items]
        fig = _default_fig("", theme)
        fig.add_trace(go.Bar(
            y=labels, x=values, orientation="h",
            marker_color=palette["rojo"], text=values, textposition="outside",
            textfont=dict(color=palette["negro"]),
        ))
        fig.update_layout(
            title=dict(text="Top incidencias", font=dict(size=16, color=palette["negro"])),
            xaxis=dict(title="Ocurrencias", dtick=1, gridcolor=palette["grid"]),
            yaxis=dict(gridcolor=palette["grid"]),
            showlegend=False, margin=dict(l=200, r=60, t=50, b=30),
        )
        fig.update_yaxes(autorange="reversed")
        return fig

    @classmethod
    def top_incidencias_json(cls, execution, logs, theme="light"):
        return cls._figure_to_dict(cls.top_incidencias(execution, logs, theme))
