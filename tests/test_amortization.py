# # tests/test_amortization.py
# import pytest
# from deepdiff import DeepDiff
# from src.adapters.contracts import CalculationPayload
# from src.adapters.amortization_adapters import TargetApiAdapter
# from src.utils.data_loader import load_test_cases
# from src.utils.financial_validators import validate_amortization_rules  # 👈 Importas la función

# TEST_CASES = load_test_cases()

# @pytest.mark.asyncio
# @pytest.mark.parametrize(
#     "case_data",
#     TEST_CASES,
#     ids=[case["case_id"] for case in TEST_CASES]
# )
# async def test_amortization_calculation_data_driven(case_data):
#     case_id = case_data["case_id"]
#     request_body = case_data["payload"]
#     expected_response = case_data["expected_response"]

#     # Validación de caso no cargado aún
#     assert len(request_body) > 0, f"[{case_id}] El payload está vacío, falta mapear."
#     assert len(expected_response) > 0, f"[{case_id}] La respuesta esperada está vacía, falta mapear."

#     # 1. Petición a la API
#     payload = CalculationPayload(case_id=case_id, parameters=request_body)
#     adapter = TargetApiAdapter()
#     result = await adapter.execute_calculation(payload)

#     # 2. Validar HTTP status
#     assert result.status_code == 200, f"[{case_id}] Error HTTP {result.status_code}: {result.data}"

#     # 3. Validar coincidencia estructural/exacta con DeepDiff
#     diff = DeepDiff(expected_response, result.data, ignore_order=True)
#     assert diff == {}, f"[{case_id}] Diferencias estructurales: {diff}"

#     # --------------------------------------------------------------------
#     # 4. VALIDACIÓN DE LAS 3 REGLAS FINANCIERAS
#     # --------------------------------------------------------------------
#     # Extraemos el monto_solicitado del payload de entrada
#     monto_solicitado = float(request_body[0]["monto_solicitado"])
    
#     # Ejecutamos las 3 comprobaciones
#     validate_amortization_rules(api_response=result.data, original_monto_solicitado=monto_solicitado)


# tests/test_amortization.py
import json
import time
import pytest
from deepdiff import DeepDiff
from src.adapters.contracts import CalculationPayload
from src.adapters.amortization_adapters import TargetApiAdapter
from src.utils.data_loader import load_test_cases
from src.utils.financial_validators import validate_amortization_rules

TEST_CASES = load_test_cases()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_data",
    TEST_CASES,
    ids=[case["case_id"] for case in TEST_CASES]
)
async def test_amortization_calculation_data_driven(case_data, request):
    case_id = case_data["case_id"]
    request_body = case_data["payload"]
    expected_response = case_data["expected_response"]

    # Validación de caso no cargado aún
    assert len(request_body) > 0, f"[{case_id}] El payload está vacío, falta mapear."
    assert len(expected_response) > 0, f"[{case_id}] La respuesta esperada está vacía, falta mapear."

    payload = CalculationPayload(case_id=case_id, parameters=request_body)
    adapter = TargetApiAdapter()

    # 1. Petición a la API
    result = await adapter.execute_calculation(payload)

    # 2. Validar HTTP status
    assert result.status_code == 200, f"[{case_id}] Error HTTP {result.status_code}: {result.data}"

    # 3. Validar coincidencia estructural/exacta con DeepDiff
    diff = DeepDiff(expected_response, result.data, ignore_order=True)
    # Se guarda el diff estructurado (aún si está vacío) para que el reporte
    # HTML/PDF pueda mostrarlo en una tabla legible en vez del dict crudo de
    # DeepDiff si esta aserción llega a fallar.
    request.node.regression_details = {
        "case_id": case_id,
        "structural_diff": json.loads(diff.to_json()) if diff else {},
    }
    assert diff == {}, f"[{case_id}] Diferencias estructurales: {diff}"

    # 4. Validar reglas financieras
    monto_solicitado = float(request_body[0]["monto_solicitado"])
    validate_amortization_rules(api_response=result.data, original_monto_solicitado=monto_solicitado)