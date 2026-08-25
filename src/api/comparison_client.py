# src/api/comparison_client.py
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

class ComparisonApiClient:
    def __init__(self):
        self.prod_base_url = os.getenv("PROD_BASE_URL", "https://msc-sofom.cloudgsf.com/msc-calculation-methods")
        self.dev_base_url = os.getenv("DEV_BASE_URL", "https://dev-msc-sofom.cloudgsf.com/msc-calculation-methods")

        self.prod_api_key = os.getenv("PROD_API_KEY", "")
        self.dev_api_key = os.getenv("DEV_API_KEY", "")

    async def post_to_both_environments(self, endpoint_path: str, payload: dict):
        """
        Envia el mismo payload a PROD y DEV en simultáneo (asyncio.gather),
        para que ninguna de las dos respuestas espere a la otra.
        """
        headers_prod = {
            "Content-Type": "application/json",
            "x-api-key": self.prod_api_key
        }

        headers_dev = {
            "Content-Type": "application/json",
            "x-api-key": self.dev_api_key
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