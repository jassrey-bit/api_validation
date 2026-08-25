from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TestStatus(Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    ERROR = "ERROR"


class CalculationPayload(BaseModel):
    case_id: str
    parameters: Any


class CalculationResult(BaseModel):
    source_name: str
    execution_time_ms: float
    status_code: int
    data: Any


class ComparisonReport(BaseModel):
    case_id: str
    status: TestStatus
    differences: List[Dict[str, Any]] = []
    prod_result: Optional[CalculationResult] = None
    dev_result: Optional[CalculationResult] = None


class IReferenceSource(ABC):
    @abstractmethod
    async def get_expected_result(self, payload: CalculationPayload) -> CalculationResult:
        pass


class IDevTarget(ABC):
    @abstractmethod
    async def get_actual_result(self, payload: CalculationPayload) -> CalculationResult:
        pass