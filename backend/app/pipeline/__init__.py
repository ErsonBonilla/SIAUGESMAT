"""Núcleo funcional puro del pipeline ETL.

Los módulos de este paquete contienen SOLO transformaciones puras:
sin acceso a base de datos, sesiones, settings, HTTP, ni efectos secundarios.

Regla de oro (guardada por tests/test_pipeline_purity.py):
- No importar app.db, SQLAlchemy, httpx, app.core.config, repositorios,
  ni invocar I/O. Cualquier dependencia externa se inyecta por parámetro.
"""
