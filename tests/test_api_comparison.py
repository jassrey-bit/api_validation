# tests/test_api_comparison.py
import pytest
from src.api.comparison_client import ComparisonApiClient
from src.utils.data_loader import load_test_cases
from src.utils.response_comparator import compare_api_responses, format_differences


client = ComparisonApiClient()
ENDPOINT_PATH = "/api/v1/simulations/get_simulation"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_data",
    load_test_cases(),
    ids=lambda c: c.get("case_id") or c.get("id") or c.get("name") or "case"
)
async def test_compare_prod_vs_dev(case_data, request):
    """
    Caso de Prueba: Comparación directa entre PROD y DEV.
    Reutiliza el payload del JSON y valida que la respuesta de DEV sea idéntica a PROD.
    """
    payload = case_data.get("payload") or case_data.get("request_body") or case_data
    case_id = case_data.get("case_id", "Desconocido")
    description = case_data.get("description", "Comparación PROD vs DEV")

    # 1. Petición a ambos entornos (simultánea)
    responses = await client.post_to_both_environments(ENDPOINT_PATH, payload)
    prod_res = responses["prod"]
    dev_res = responses["dev"]

    # 2. Comparación de respuestas
    comparison = compare_api_responses(prod_res, dev_res)

    # 3. Guardar detalles en el objeto del test para el reporte HTML/PDF
    request.node.comparison_details = {
        "case_id": case_id,
        "description": description,
        "payload": payload,
        "prod_response": prod_res,
        "dev_response": dev_res,
        "differences": comparison["differences"],
        "is_equal": comparison["is_equal"]
    }

    # 4. Aserción
    if not comparison["is_equal"]:
        pytest.fail(
            f"Diferencias encontradas entre PROD y DEV:\n{format_differences(comparison['differences'])}"
        )