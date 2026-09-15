# src/api/comparison_client.py
import asyncio
import httpx

from config.settings import Settings, settings as default_settings


class ComparisonApiClient:
    def __init__(self, settings: Settings = default_settings):
        self.prod_base_url = settings.PROD_BASE_URL
        self.dev_base_url = settings.DEV_BASE_URL

        self.prod_api_key = settings.PROD_API_KEY
        self.dev_api_key = settings.DEV_API_KEY

    async def post_to_both_environments(self, endpoint_path: str, payload: dict):
        """
        Envia el mismo payload a PROD y DEV en simultáneo (asyncio.gather),
        para que ninguna de las dos respuestas espere a la otra.
        """
        headers_prod = {
            "Content-Type": "application/json",
            "Simulation-API-Key": self.prod_api_key
        }

        headers_dev = {
            "Content-Type": "application/json",
            "Simulation-API-Key": self.dev_api_key
        }

        url_prod = f"{self.prod_base_url}{endpoint_path}"
        url_dev = f"{self.dev_base_url}{endpoint_path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            res_prod, res_dev = await asyncio.gather(
                client.post(url_prod, json=payload, headers=headers_prod),
                client.post(url_dev, json=payload, headers=headers_dev),
            )

        def _safe_json(response):
            try:
                return response.json()
            except Exception:
                return response.text

        return {
            "prod": {
                "status_code": res_prod.status_code,
                "response_time_ms": int(res_prod.elapsed.total_seconds() * 1000),
                "data": _safe_json(res_prod)
            },
            "dev": {
                "status_code": res_dev.status_code,
                "response_time_ms": int(res_dev.elapsed.total_seconds() * 1000),
                "data": _safe_json(res_dev)
            }
        }