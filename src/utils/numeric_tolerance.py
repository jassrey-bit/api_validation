# src/utils/numeric_tolerance.py
"""Redondea, antes de comparar, únicamente los campos numéricos que sabemos
que sufren ruido de precisión flotante en la API (por ahora solo 'cat').

A propósito NO se aplica una tolerancia global a todo número de la
respuesta: eso enmascararía diferencias reales en campos que deben ser
exactos (conteos de días, número de amortización, montos, etc.)."""
from __future__ import annotations

from typing import Any

TOLERANCE_FIELDS = {"cat"}


def apply_decimal_tolerance(data: Any, decimals: int, fields: set[str] = TOLERANCE_FIELDS) -> Any:
    """Devuelve una copia de `data` con los valores numéricos bajo alguna
    llave en `fields` (comparación case-insensitive) redondeados a
    `decimals` decimales. El resto de la estructura queda intacta."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            is_tolerance_field = key.lower() in fields
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if is_tolerance_field and is_number:
                result[key] = round(value, decimals)
            else:
                result[key] = apply_decimal_tolerance(value, decimals, fields)
        return result
    if isinstance(data, list):
        return [apply_decimal_tolerance(item, decimals, fields) for item in data]
    return data
