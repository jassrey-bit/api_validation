"""Traduce las rutas técnicas de DeepDiff (root[0]['campo']) a filas
legibles para los reportes. Comparte el mismo diccionario de nombres de
campo que el visor de diffs del frontend (src/lib/apiDiffFormat.ts en
qa-platform-web) — si agregas un campo ahí, agrégalo también aquí."""
from __future__ import annotations

import re

FIELD_LABELS = {
    "pago_fijo": "Pago fijo",
    "pago_fijo_auxiliar": "Pago fijo (auxiliar)",
    "capital": "Capital",
    "iva_capital": "IVA sobre capital",
    "interes_ordinario": "Interés ordinario",
    "iva": "IVA",
    "tasa_iva": "Tasa + IVA",
    "interes_gracia": "Interés de gracia",
    "iva_gracia": "IVA de gracia",
    "capital_diferido": "Capital diferido",
    "saldo_insoluto": "Saldo insoluto",
    "dias_periodo": "Días del periodo",
    "fecha_inicio": "Fecha de inicio",
    "fecha_vencimiento": "Fecha de vencimiento",
    "num_amortizacion": "Número de amortización",
    "guid_simulacion": "GUID de simulación",
    "GUID_Simulacion": "GUID de simulación",
    "monto_financiado": "Monto financiado",
    "monto_dispuesto": "Monto dispuesto",
    "cat": "CAT",
    "status_code": "Código de respuesta HTTP",
}

_TOKEN_RE = re.compile(r"\[(?:'([^']*)'|\"([^\"]*)\"|(\d+))\]")


def _field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _tokenize(path: str) -> list:
    tokens: list = []
    for m in _TOKEN_RE.finditer(path):
        if m.group(3) is not None:
            tokens.append(int(m.group(3)))
        else:
            tokens.append(m.group(1) if m.group(1) is not None else m.group(2))
    return tokens


def humanize_diff_path(path: str) -> str:
    tokens = _tokenize(path)
    if not tokens:
        return path

    if "amortizaciones" in tokens:
        idx = len(tokens) - 1 - tokens[::-1].index("amortizaciones")
        if idx + 1 < len(tokens) and isinstance(tokens[idx + 1], int):
            field = tokens[-1]
            if isinstance(field, str):
                return f"Amortización {tokens[idx + 1] + 1} → {_field_label(field)}"

    last = tokens[-1]
    return _field_label(last) if isinstance(last, str) else path


def parse_structural_diff(diff: dict | None) -> list[dict]:
    """Convierte el dict de DeepDiff.to_json() en filas
    {label, change_label, before, after} legibles, deduplicando cambios que
    aparecen dos veces por la tabla de amortización duplicada en la
    respuesta (anidada y "aplanada" a la vez)."""
    if not diff:
        return []

    rows = []

    for path, v in (diff.get("values_changed") or {}).items():
        rows.append({
            "label": humanize_diff_path(path), "change_label": "Valor distinto",
            "before": v.get("old_value"), "after": v.get("new_value"),
        })

    for path, v in (diff.get("type_changes") or {}).items():
        rows.append({
            "label": humanize_diff_path(path), "change_label": "Tipo de dato distinto",
            "before": v.get("old_value"), "after": v.get("new_value"),
        })

    for path, v in (diff.get("iterable_item_added") or {}).items():
        rows.append({"label": humanize_diff_path(path), "change_label": "Agregado", "before": None, "after": v})

    for path, v in (diff.get("iterable_item_removed") or {}).items():
        rows.append({"label": humanize_diff_path(path), "change_label": "Eliminado", "before": v, "after": None})

    for path in diff.get("dictionary_item_added") or []:
        rows.append({"label": humanize_diff_path(path), "change_label": "Campo agregado", "before": None, "after": None})

    for path in diff.get("dictionary_item_removed") or []:
        rows.append({"label": humanize_diff_path(path), "change_label": "Campo eliminado", "before": None, "after": None})

    seen = set()
    deduped = []
    for r in rows:
        key = (r["label"], r["change_label"], repr(r["before"]), repr(r["after"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped
