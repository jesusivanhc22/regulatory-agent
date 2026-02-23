def generate_executive_summary(publications):

    report = "# REPORTE EJECUTIVO - IMPACTO ERP FARMACIAS\n\n"

    if not publications:
        report += "No se detectaron impactos relevantes.\n"
        return report

    # Contadores
    alta_count = sum(1 for p in publications if p["severity"] == "ALTA")
    media_count = sum(1 for p in publications if p["severity"] == "MEDIA")
    report += f"**Total con impacto: {len(publications)}** (ALTA: {alta_count} | MEDIA: {media_count})\n\n"
    report += "---\n\n"

    for pub in publications:
        severity = pub["severity"]
        tag = "[ALTA]" if severity == "ALTA" else "[MEDIA]"

        report += f"## {tag} {pub['title']}\n"
        report += f"- **URL:** {pub['url']}\n"
        report += f"- **Dominio:** {pub['primary_domain']} | "
        report += f"**Modulo:** {pub['impacted_module']} | "
        report += f"**Severidad:** {severity}\n"

        # Scores de dominio
        h = pub["health_score"] or 0
        f = pub["fiscal_score"] or 0
        r = pub["retail_score"] or 0
        report += f"- Scores dominio: H={h} F={f} R={r}\n"

        # Scores de modulo ERP
        inv = pub["invoicing_score"] or 0
        tax = pub["tax_reporting_score"] or 0
        invent = pub["inventory_score"] or 0
        acc = pub["accounting_score"] or 0
        pos = pub["pos_score"] or 0
        try:
            reg = pub["regulatory_compliance_score"] or 0
        except (IndexError, KeyError):
            reg = 0
        report += f"- Scores modulo: INV={inv} TAX={tax} INVENT={invent} ACC={acc} POS={pos} REG={reg}\n"

        # Obligation
        obl = pub["operational_obligation_score"] or 0
        report += f"- Obligation score: {obl}\n"
        report += f"- Motivo: {pub['impact_reason']}\n\n"

    return report
