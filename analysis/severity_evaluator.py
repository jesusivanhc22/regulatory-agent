def evaluate_severity(domain_scores: dict,
                      obligation_score: int,
                      module_scores: dict) -> str:
    """
    Determina la severidad del impacto usando score combinado.

    Score = max_domain + obligation_score + max_module
    Esto permite que una señal muy fuerte de dominio + módulo ERP
    compense una obligación baja (y viceversa).
    """

    max_domain = max(domain_scores.values()) if domain_scores else 0
    max_module = max(module_scores.values()) if module_scores else 0

    combined_score = max_domain + obligation_score + max_module

    # ALTA: score combinado alto Y al menos dominio y módulo presentes
    if combined_score >= 7 and max_domain >= 2 and max_module >= 1:
        return "ALTA"

    # MEDIA: score combinado moderado Y al menos dominio y módulo presentes
    if combined_score >= 4 and max_domain >= 2 and max_module >= 1:
        return "MEDIA"

    # Todo lo demás
    return "BAJA"
