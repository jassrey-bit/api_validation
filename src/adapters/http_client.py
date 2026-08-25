import time
from typing import Any, Dict, List, Optional
import httpx
from src.domain.models import CalculationResult


class AsyncHttpClient:
    """Cliente HTTP reutilizable basado en httpx con medición de tiempo."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def post(
        self,
        url: str,
        payload: Any,  # Puede ser tanto dict como list
        source_name: str,
        headers: Optional[Dict[str, str]] = None,  # <--- Agregado parámetro headers
    ) -> CalculationResult:
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Se agregan los headers a la petición httpx
                response = await client.post(
                    url, json=payload, headers=headers
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                return CalculationResult(
                    source_name=source_name,
                    execution_time_ms=round(elapsed_ms, 2),
                    status_code=response.status_code,
                    data=(
                        response.json()
                        if response.is_success
                        else {"error": response.text}
                    ),
                )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return CalculationResult(
                source_name=source_name,
                execution_time_ms=round(elapsed_ms, 2),
                status_code=500,
                data={"error": str(e)},
            )