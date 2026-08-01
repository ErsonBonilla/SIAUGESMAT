# Pruebas reales contra Moodle 3.9

Scripts para probar el pipeline ETL completo contra la instancia real de Moodle (`tuaulavirtual.ut.edu.co`).

## Requisitos

- Backend corriendo (`docker compose up -d backend worker`)
- Python 3.12 con dependencias del backend instaladas

## Uso

```bash
# Modo seguro — solo usuarios (no toca cursos)
python tests_e2e/run_test.py tests_e2e/fixtures/ibague.xlsx

# Modo users + courses — requiere confirmación de delete masivo
python tests_e2e/run_test.py tests_e2e/fixtures/ibague.xlsx --mode both

# Con confirmación automática del delete masivo
python tests_e2e/run_test.py tests_e2e/fixtures/ibague.xlsx --mode both --confirm

# Semestre personalizado
python tests_e2e/run_test.py tests_e2e/fixtures/uraba.xlsx --semester 2026B --mode users
```

## Fixtures disponibles

| Archivo | Filas | Programa |
|---------|-------|----------|
| `bajocalima.xlsx` | 9 | Tecnología Forestal + Admin Financiera |
| `ibague.xlsx` | 8 | Especialización Virtual (POSGRADO) |
| `uraba.xlsx` | 10 | Admin Financiera Urabá |

## Funcionamiento

1. `conftest.py` genera un token JWT firmado (sin login Moodle)
2. `run_test.py` sube el Excel, dispara el ETL y espera resultados
3. Si el plan incluye >500 eliminaciones, se detiene y pide `--confirm`

## Salida

```
SIAUGESMAT — Prueba real
  Archivo:   ibague.xlsx
  Mode:      users
  Semestre:  2026B

Subiendo archivo...
  Upload OK → execution_id=14
Procesando...
  [running] 2% Consultando categorías…
  [running] 14% Análisis de datos completado
  [completed] 100% Ejecución completada

==================================================
Resultados — Ejecución #14
  Status:     completed
  Progreso:   100%
  Duración:   42.0s
  Errores:    0
  users_created:  0

✅ Pipeline completado exitosamente.
```
