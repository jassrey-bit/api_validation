from abc import ABC, abstractmethod
from typing import List
from src.domain.models import CalculationPayload, CalculationResult


class IPayloadProvider(ABC):
    """Interfaz para cargar escenarios (desde Archivo, Código o BD)."""
    
    @abstractmethod
    def load_payloads(self) -> List[CalculationPayload]:
        """Obtiene la lista de escenarios a ejecutar."""
        pass


class IReferenceSource(ABC):
    """Interfaz para obtener la Fuente de Verdad (Prod API, Archivo Baseline, etc.)."""
    
    @abstractmethod
    async def get_expected_result(self, payload: CalculationPayload) -> CalculationResult:
        """Obtiene el resultado esperado/referencia."""
        pass


class IDevTarget(ABC):
    """Interfaz para ejecutar peticiones sobre el ambiente objetivo (Dev API, etc.)."""
    
    @abstractmethod
    async def execute_calculation(self, payload: CalculationPayload) -> CalculationResult:
        """Ejecuta el cálculo en el ambiente objetivo."""
        pass