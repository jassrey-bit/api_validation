"""Lógica de ejecución de casos, extraída de tests/test_amortization.py y
tests/test_api_comparison.py para poder invocarse directamente desde el
servicio FastAPI (api/jobs.py), sin depender de pytest ni de un subprocess."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from deepdiff import DeepDiff

from src.adapters.amortization_adapters import TargetApiAdapter
from src.adapters.contracts import CalculationPayload
from src.api.comparison_client import ComparisonApiClient
from src.utils.financial_validators import validate_amortization_rules
from src.utils.numeric_tolerance import TOLERANCE_FIELDS, apply_decimal_tolerance
from src.utils.response_comparator import compare_api_responses

ENDPOINT_PATH = "/api/v1/simulations/get_simulation"
_MAX_CONCURRENT_REQUESTS = 5


def _try_extract_monto(payload: Any) -> float | None:
    try:
        return float(payload[0]["monto_solicitado"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _resolve_tolerance_fields(tolerance_fields: list[str] | None) -> set[str]:
    """`None` -> usa el default (solo 'cat'); una lista (incluso vacía, si el
    usuario desactivó todos los campos en Ajustes) -> se respeta tal cual."""
    if tolerance_fields is None:
        return TOLERANCE_FIELDS
    return {f.lower() for f in tolerance_fields}


def _safe_validate(api_response: Any, monto_solicitado: float | None) -> list[str]:
    """Envuelve validate_amortization_rules en try/except para que un caso sin
    monto_solicitado extraíble (p.ej. un payload personalizado con otra forma)
    no reviente el resto de la corrida."""
    if monto_solicitado is None:
        return []
    try:
        validate_amortization_rules(api_response=api_response, original_monto_solicitado=monto_solicitado)
    except AssertionError as e:
        return [str(e)]
    except Exception as e:
        return [f"No se pudo validar las reglas financieras: {e}"]
    return []


async def run_regression_case(
    case: dict,
    tolerance_decimals: int | None = None,
    tolerance_fields: list[str] | None = None,
) -> dict:
    """Un caso contra la API bajo prueba: diff estructural (DeepDiff) contra
    expected_response + las 3 reglas financieras."""
    case_id = case["case_id"]
    request_body = case["payload"]
    expected_response = case.get("expected_response")

    payload = CalculationPayload(case_id=case_id, parameters=request_body)
    result = await TargetApiAdapter().execute_calculation(payload)

    # Solo se tolera ruido de redondeo en los campos activados en Ajustes
    # (ver numeric_tolerance.py); el resto se compara exacto, así que se
    # redondea una copia sin tocar expected_response/result.data, que se
    # devuelven íntegros.
    diff_expected, diff_actual = expected_response, result.data
    if tolerance_decimals is not None:
        fields = _resolve_tolerance_fields(tolerance_fields)
        diff_expected = apply_decimal_tolerance(expected_response, tolerance_decimals, fields)
        diff_actual = apply_decimal_tolerance(result.data, tolerance_decimals, fields)

    diff = DeepDiff(diff_expected, diff_actual, ignore_order=True)
    monto_solicitado = _try_extract_monto(request_body)
    violations = _safe_validate(result.data, monto_solicitado)

    passed = result.status_code == 200 and not diff and not violations

    return {
        "case_id": case_id,
        "description": case.get("description", ""),
        "passed": passed,
        "http_status": result.status_code,
        "execution_time_ms": result.execution_time_ms,
        "structural_diff": json.loads(diff.to_json()) if diff else {},
        "financial_violations": violations,
        "actual_response": result.data,
        "expected_response": expected_response,
    }


async def run_comparison_case(
    case: dict,
    tolerance_decimals: int | None = None,
    tolerance_fields: list[str] | None = None,
) -> dict:
    """Un caso enviado simultáneamente a PROD y DEV: diff estructural
    (response_comparator) + reglas financieras evaluadas en ambos lados."""
    payload = case.get("payload") or case.get("request_body") or case
    responses = await ComparisonApiClient().post_to_both_environments(ENDPOINT_PATH, payload)

    # Igual que en regresión: solo se tolera redondeo en los campos activados
    # en Ajustes, sobre copias usadas nada más para el diff; "prod"/"dev" en
    # la respuesta final conservan los valores originales sin redondear.
    prod_for_diff, dev_for_diff = responses["prod"], responses["dev"]
    if tolerance_decimals is not None:
        fields = _resolve_tolerance_fields(tolerance_fields)
        prod_for_diff = {**responses["prod"], "data": apply_decimal_tolerance(responses["prod"]["data"], tolerance_decimals, fields)}
        dev_for_diff = {**responses["dev"], "data": apply_decimal_tolerance(responses["dev"]["data"], tolerance_decimals, fields)}

    comparison = compare_api_responses(prod_for_diff, dev_for_diff)
    monto_solicitado = _try_extract_monto(payload)

    prod_violations = _safe_validate(responses["prod"]["data"], monto_solicitado)
    dev_violations = _safe_validate(responses["dev"]["data"], monto_solicitado)

    return {
        "case_id": case.get("case_id", "personalizado"),
        "description": case.get("description", "Comparación PROD vs DEV"),
        "passed": comparison["is_equal"] and not prod_violations and not dev_violations,
        "prod": {**responses["prod"], "financial_violations": prod_violations},
        "dev": {**responses["dev"], "financial_violations": dev_violations},
        "differences": comparison["differences"],
    }


async def run_batch(
    mode: Literal["regression", "comparison"],
    cases: list[dict],
    tolerance_decimals: int | None = None,
    tolerance_fields: list[str] | None = None,
) -> list[dict]:
    fn = run_regression_case if mode == "regression" else run_comparison_case
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

    async def _bounded(case: dict) -> dict:
        async with semaphore:
            return await fn(case, tolerance_decimals=tolerance_decimals, tolerance_fields=tolerance_fields)

    return await asyncio.gather(*(_bounded(case) for case in cases))
