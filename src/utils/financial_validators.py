# src/utils/financial_validators.py
import pytest


def validate_amortization_rules(api_response: list, original_monto_solicitado: float):
    """
    Valida las 3 reglas de negocio sobre la tabla de amortización recibida.
    
    Regla 1: Suma de abonos a capital == Importe de crédito (monto_solicitado)
    Regla 2: Por cada amortización -> capital + interes + iva + interes_gracia + iva_gracia == pago_fijo
    Regla 3: Suma total de TODOS los componentes (incluyendo gracia) == Suma total de pagos fijos
    """
    
    # Extraemos la lista de amortizaciones de la respuesta
    amortizaciones = []
    if isinstance(api_response, list) and len(api_response) > 0:
        conceptos = api_response[0].get("amortizacion_conceptos", [])
        if conceptos:
            amortizaciones = conceptos[0].get("amortizaciones", [])

    assert len(amortizaciones) > 0, "No se encontraron amortizaciones en la respuesta para validar."

    # Acumuladores de totales globales
    total_capital = 0.0
    total_interes = 0.0
    total_iva = 0.0
    total_interes_gracia = 0.0  
    total_iva_gracia = 0.0    
    total_pagos_fijos = 0.0

    # Iteramos sobre cada amortización (renglón por renglón)
    for amort in amortizaciones:
        num = amort.get("num_amortizacion")
        
        capital = float(amort.get("capital", 0.0))
        interes = float(amort.get("interes_ordinario", 0.0))
        iva = float(amort.get("iva", 0.0))
        interes_gracia = float(amort.get("interes_gracia", 0.0))
        iva_gracia = float(amort.get("iva_gracia", 0.0))
        pago_fijo = float(amort.get("pago_fijo", 0.0))

        # Acumulamos todos los conceptos en los totales globales
        total_capital += capital
        total_interes += interes
        total_iva += iva
        total_interes_gracia += interes_gracia
        total_iva_gracia += iva_gracia
        total_pagos_fijos += pago_fijo

        # ------------------------------------------------------------------
        # REGLA 2: Capital + Interés + IVA + Int. Gracia + IVA Gracia == Pago Fijo
        # ------------------------------------------------------------------
        suma_renglon = capital + interes + iva + interes_gracia + iva_gracia
        assert suma_renglon == pytest.approx(pago_fijo, abs=0.01), (
            f"Regla 2 Falló en Amortización #{num}: "
            f"Capital({capital}) + Interés({interes}) + IVA({iva}) + "
            f"Int.Gracia({interes_gracia}) + IVA.Gracia({iva_gracia}) = {suma_renglon:.2f}, "
            f"pero el Pago Fijo registrado es {pago_fijo:.2f}"
        )

    # ------------------------------------------------------------------
    # REGLA 1: Suma de abonos a capital == Importe de crédito
    # ------------------------------------------------------------------
    assert total_capital == pytest.approx(original_monto_solicitado, abs=0.01), (
        f"Regla 1 Falló: La suma total del capital amortizado ({total_capital:.2f}) "
        f"no coincide con el monto de crédito solicitado ({original_monto_solicitado:.2f})"
    )

    # ------------------------------------------------------------------
    # REGLA 3: Suma global de TODOS los componentes == Suma de pagos fijos
    # ------------------------------------------------------------------
    suma_totales = (
        total_capital 
        + total_interes 
        + total_iva 
        + total_interes_gracia 
        + total_iva_gracia
    )
    
    assert suma_totales == pytest.approx(total_pagos_fijos, abs=0.10), (
        f"Regla 3 Falló: Suma de Totales ("
        f"Cap:{total_capital:.2f} + Int:{total_interes:.2f} + IVA:{total_iva:.2f} + "
        f"Int.Gracia:{total_interes_gracia:.2f} + IVA.Gracia:{total_iva_gracia:.2f} = {suma_totales:.2f}) "
        f"no es igual a la suma de todos los Pagos Fijos ({total_pagos_fijos:.2f})"
    )