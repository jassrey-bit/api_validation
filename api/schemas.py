from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class CustomCase(BaseModel):
    """Caso de prueba pegado/subido por el usuario en la UI, en vez de un fixture existente."""

    case_id: str = "personalizado"
    description: str = "Caso personalizado"
    payload: Any
    expected_response: Any | None = None


class CreateRunRequest(BaseModel):
    mode: Literal["regression", "comparison"]
    case_ids: list[str] | None = None
    custom_cases: list[CustomCase] | None = None
    tolerance_decimals: int | None = None
    tolerance_fields: list[str] | None = None


class RunSummaryOut(BaseModel):
    total: int
    passed: int
    failed: int
