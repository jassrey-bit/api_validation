# src/utils/data_loader.py
import json
import os
from pathlib import Path

import pytest


def load_test_cases(fixtures_dir: str = "tests/fixtures") -> list:
    """
    Carga todos los casos de prueba desde los archivos JSON ubicados en fixtures_dir.
    Fuente única compartida por el flujo de regresión y el de comparación PROD vs DEV,
    para garantizar que ambos usen exactamente los mismos payloads.
    """
    abs_dir = Path(__file__).parent.parent.parent / fixtures_dir

    if not abs_dir.exists():
        pytest.skip(f"No se encontró el directorio de fixtures en: {abs_dir}")

    all_cases = []
    for filename in sorted(os.listdir(abs_dir)):
        if filename.endswith(".json"):
            with open(abs_dir / filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_cases.extend(data)
                elif isinstance(data, dict) and "test_cases" in data:
                    all_cases.extend(data["test_cases"])
                elif isinstance(data, dict):
                    all_cases.append(data)
    return all_cases