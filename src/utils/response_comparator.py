# src/utils/response_comparator.py
import re

# La respuesta de la API duplica la tabla de amortización (anidada bajo
# amortizacion_conceptos y otra vez "aplanada" a nivel raíz), así que un
# mismo cambio real aparece dos veces con paths distintos apuntando al mismo
# valor. Se normaliza el path anidado a la forma "aplanada" para poder
# deduplicar antes de mostrar el reporte.
_AMORT_NESTED_RE = re.compile(r"^(root\[\d+\])\.amortizacion_conceptos\[\d+\]\.(amortizaciones\[\d+\]\..+)$")


def _canonicalize_diff_path(path: str) -> str:
    match = _AMORT_NESTED_RE.match(path)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return path


def _dedupe_differences(differences: list) -> list:
    seen = set()
    deduped = []
    for d in differences:
        key = (_canonicalize_diff_path(d["path"]), d["type"], repr(d.get("prod_value")), repr(d.get("dev_value")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)
    return deduped


def compare_api_responses(prod_res: dict, dev_res: dict) -> dict:
    """
    Compara las respuestas de PROD y DEV.
    Devuelve un diccionario con 'is_equal', 'differences' (lista de diffs
    estructurados: path/type/prod_value/dev_value) y 'differences_text'
    (la misma información en formato de texto plano, para logs/asserts).

    La comparación es exacta: si se quiere tolerar ruido de redondeo en
    campos puntuales (p. ej. 'cat'), se debe pre-redondear esos campos en
    prod_res/dev_res antes de llamar a esta función (ver
    src/utils/numeric_tolerance.py), en vez de aplicar una tolerancia
    genérica aquí que enmascararía diferencias reales en otros campos.
    """
    differences = []

    # 1. Comparar Status Code
    if prod_res["status_code"] != dev_res["status_code"]:
        differences.append({
            "path": "status_code",
            "type": "value_changed",
            "prod_value": prod_res["status_code"],
            "dev_value": dev_res["status_code"],
        })

    # 2. Comparar el contenido JSON/Data
    prod_data = prod_res["data"]
    dev_data = dev_res["data"]

    if type(prod_data) != type(dev_data):
        differences.append({
            "path": "(tipo de dato raíz)",
            "type": "type_mismatch",
            "prod_value": type(prod_data).__name__,
            "dev_value": type(dev_data).__name__,
        })
    elif isinstance(prod_data, dict) and isinstance(dev_data, dict):
        _compare_dicts(prod_data, dev_data, path="", differences=differences)
    elif isinstance(prod_data, list) and isinstance(dev_data, list):
        _compare_lists(prod_data, dev_data, path="root", differences=differences)
    elif prod_data != dev_data:
        differences.append({
            "path": "(respuesta raíz)",
            "type": "value_changed",
            "prod_value": prod_data,
            "dev_value": dev_data,
        })

    differences = _dedupe_differences(differences)
    is_equal = len(differences) == 0

    return {
        "is_equal": is_equal,
        "differences": differences,
        "differences_text": [_format_diff(d) for d in differences],
    }


def format_differences(differences: list) -> str:
    """Formatea una lista de diffs estructurados como texto plano (para asserts/logs)."""
    return "\n".join(f"  - {_format_diff(d)}" for d in differences)


def _format_diff(d: dict) -> str:
    path = d["path"]
    if d["type"] == "missing_in_prod":
        return f"Campo '{path}' falta en PROD"
    if d["type"] == "missing_in_dev":
        return f"Campo '{path}' falta en DEV"
    if d["type"] == "length_mismatch":
        return f"Longitud de lista diferente en '{path}' -> PROD: {d['prod_value']}, DEV: {d['dev_value']}"
    if d["type"] == "type_mismatch":
        return f"Tipo de dato diferente -> PROD: {d['prod_value']}, DEV: {d['dev_value']}"
    return f"Valor diferente en '{path}' -> PROD: {d['prod_value']} | DEV: {d['dev_value']}"


def _compare_dicts(d1: dict, d2: dict, path: str, differences: list):
    """Función recursiva para comparar llaves y valores en JSONs anidados."""
    all_keys = sorted(set(d1.keys()).union(set(d2.keys())), key=str)

    for key in all_keys:
        current_path = f"{path}.{key}" if path else key

        if key not in d1:
            differences.append({
                "path": current_path, "type": "missing_in_prod",
                "prod_value": None, "dev_value": d2[key],
            })
        elif key not in d2:
            differences.append({
                "path": current_path, "type": "missing_in_dev",
                "prod_value": d1[key], "dev_value": None,
            })
        else:
            val1 = d1[key]
            val2 = d2[key]

            if isinstance(val1, dict) and isinstance(val2, dict):
                _compare_dicts(val1, val2, current_path, differences)
            elif isinstance(val1, list) and isinstance(val2, list):
                _compare_lists(val1, val2, current_path, differences)
            elif val1 != val2:
                differences.append({
                    "path": current_path, "type": "value_changed",
                    "prod_value": val1, "dev_value": val2,
                })


def _compare_lists(l1: list, l2: list, path: str, differences: list):
    """Compara listas elemento por elemento o por tamaño."""
    if len(l1) != len(l2):
        differences.append({
            "path": path, "type": "length_mismatch",
            "prod_value": f"{len(l1)} elementos", "dev_value": f"{len(l2)} elementos",
        })
        return

    for idx, (item1, item2) in enumerate(zip(l1, l2)):
        item_path = f"{path}[{idx}]"
        if isinstance(item1, dict) and isinstance(item2, dict):
            _compare_dicts(item1, item2, item_path, differences)
        elif isinstance(item1, list) and isinstance(item2, list):
            _compare_lists(item1, item2, item_path, differences)
        elif item1 != item2:
            differences.append({
                "path": item_path, "type": "value_changed",
                "prod_value": item1, "dev_value": item2,
            })
