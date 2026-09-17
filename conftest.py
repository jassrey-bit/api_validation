# conftest.py
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import pytest

# Configuración de rutas para importaciones locales
root_dir = Path(__file__).parent.resolve()
src_dir = root_dir / "src"

sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(src_dir))

# Importamos la función de generación de reporte
from src.utils.report_generator import generate_execution_reports
from src.utils.diff_formatting import parse_structural_diff

# Variable global para guardar los resultados de cada test durante la sesión
session_test_results = []
session_start_time = 0.0

def pytest_sessionstart(session):
    """Captura el momento exacto en que inicia la suite de pruebas."""
    global session_start_time
    session_start_time = time.time()


def pytest_html_report_title(report):
    """Cambia el título del reporte HTML nativo si se genera."""
    report.title = "Reporte de Pruebas de Regresión - API Amortización"


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook que se ejecuta en cada prueba. Captura el resultado (PASSED/FAILED),
    la duración real en milisegundos, el ID del caso y la descripción.
    """
    outcome = yield
    report = outcome.get_result()

    # Solo registramos cuando la prueba termina la fase principal de ejecución ('call')
    if report.when == "call":
        status = "PASSED" if report.passed else "FAILED"
        
        # CAPTURAMOS AUTOMÁTICAMENTE EL TIEMPO EN MS MEDIANTE PYTEST
        response_time_ms = int(report.duration * 1000)
        
        # 1. Obtener la descripción del caso desde el parámetro case_data (JSON)
        description = "Sin descripción disponible"
        if hasattr(item, "callspec") and "case_data" in item.callspec.params:
            case_data = item.callspec.params["case_data"]
            if isinstance(case_data, dict):
                description = case_data.get("description", description)
        elif item.obj.__doc__:
            description = item.obj.__doc__.strip()

        # 2. Obtener el nombre o ID del test
        test_name = item.callspec.id if hasattr(item, "callspec") and hasattr(item.callspec, "id") else item.name

        # 3. Mantenemos tu estructura idéntica
        test_info = {
            "name": str(test_name).replace("test_", "").replace("_", " ").title(),
            "description": description,
            "status": status,
            "response_time_ms": response_time_ms,
            "error_log": str(report.longrepr) if report.failed else ""
        }

        # 🔹 ADICIÓN SEGURA (NO ROMPE NADA):
        # Si la prueba es del tipo comparación DEV vs PROD, capturamos sus detalles extendidos
        comparison_details = getattr(item, "comparison_details", None)
        if comparison_details:
            test_info["comparison_details"] = comparison_details

        # Si es una prueba de regresión con diferencias estructurales (DeepDiff),
        # las traducimos a filas legibles para el reporte HTML/PDF.
        regression_details = getattr(item, "regression_details", None)
        if regression_details:
            test_info["diff_rows"] = parse_structural_diff(regression_details.get("structural_diff"))
        
        session_test_results.append(test_info)


# conftest.py (Sección de pytest_sessionfinish)

def pytest_sessionfinish(session, exitstatus):
    """
    Genera un reporte por cada tipo de prueba ejecutada en la sesión:
    regresión (contra fixture fijo) y/o comparación (PROD vs DEV en vivo).
    Se generan por separado para no mezclar resultados de naturaleza distinta
    en un mismo reporte.
    """
    now = datetime.now()
    duration_sec = round(time.time() - session_start_time, 2) if session_start_time else 0.0
    total_suite_duration = f"{duration_sec}s"

    year_month = now.strftime("%Y-%m")
    day = now.strftime("%d")
    execution_date = now.strftime("%Y-%m-%d")
    execution_time = now.strftime("%H:%M:%S")

    # Estructura de carpetas: reports/YYYY-MM/DD/
    output_dir = os.path.join("reports", year_month, day)

    regression_results = [t for t in session_test_results if "comparison_details" not in t]
    comparison_results = [t for t in session_test_results if "comparison_details" in t]

    common_kwargs = dict(
        output_dir=output_dir,
        execution_date=execution_date,
        execution_time=execution_time,
        total_suite_duration=total_suite_duration,
    )

    if regression_results:
        _build_report(
            results=regression_results,
            report_type="regression",
            report_prefix="reporte_regresion_amortizacion",
            report_title="Reporte de Regresión - API Amortización",
            reference_source="Archivo de Referencia (JSON)",
            target_env="PROD",
            **common_kwargs,
        )

    if comparison_results:
        _build_report(
            results=comparison_results,
            report_type="comparison",
            report_prefix="reporte_comparacion_prod_vs_dev",
            report_title="Reporte de Comparación Directa - PROD vs DEV",
            reference_source="PROD (Ambiente Referencia)",
            target_env="PROD vs DEV",
            **common_kwargs,
        )


def _build_report(
    results, report_type, report_prefix, report_title, reference_source, target_env,
    output_dir, execution_date, execution_time, total_suite_duration,
):
    total = len(results)
    passed = sum(1 for t in results if t["status"] == "PASSED")
    failed = sum(1 for t in results if t["status"] == "FAILED")
    coincidence_pct = round((passed / total * 100), 2) if total > 0 else 0.0

    report_data = {
        "report_title": report_title,
        "execution_date": execution_date,
        "execution_time": execution_time,
        "total_suite_duration": total_suite_duration,
        "http_method": "POST",
        "endpoint_path": "/api/v1/simulations/get_simulation",
        "reference_source": reference_source,
        "target_env": target_env,
        "total_scenarios": total,
        "coincidence_percentage": coincidence_pct,
        "failed_rules": failed,
        "test_results": results,
    }

    if report_type == "comparison":
        prod_times = [
            t["comparison_details"]["prod_response"]["response_time_ms"]
            for t in results if t.get("comparison_details")
        ]
        dev_times = [
            t["comparison_details"]["dev_response"]["response_time_ms"]
            for t in results if t.get("comparison_details")
        ]
        if prod_times and dev_times:
            report_data["avg_latency_delta_ms"] = round(
                (sum(dev_times) / len(dev_times)) - (sum(prod_times) / len(prod_times)), 2
            )

    try:
        generate_execution_reports(
            report_data, output_dir=output_dir, report_prefix=report_prefix, report_type=report_type
        )
        print(f"\n-> Reportes '{report_prefix}' creados exitosamente en {output_dir}")
    except Exception as e:
        print(f"-> Error al generar el reporte personalizado ({report_prefix}): {e}")