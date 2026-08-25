from src.adapters.contracts import CalculationPayload
from src.adapters.http_client import AsyncHttpClient
from config.settings import settings


class TargetApiAdapter:
    def __init__(
        self, 
        endpoint_url: str = settings.API_URL, 
        api_key: str = settings.API_KEY
    ):
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.http_client = AsyncHttpClient(timeout=15.0)

    async def execute_calculation(self, payload: CalculationPayload) -> tuple[int, dict | list]:
        headers = {
            "Simulation-API-Key": self.api_key,
            "Content-Type": "application/json",
            "accept": "*/*",
        }
        # Extraemos los parámetros del payload para enviarlos como JSON
        return await self.http_client.post(
            url=self.endpoint_url,
            payload=payload.parameters,
            headers=headers,
            source_name="API_UNDER_TEST",
        )