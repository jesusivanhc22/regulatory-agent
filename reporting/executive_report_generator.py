def generate_executive_summary(publications):

    report = "# REPORTE EJECUTIVO – IMPACTO ERP FARMACIAS\n\n"

    if not publications:
        report += "No se detectaron impactos relevantes.\n"
        return report

    for pub in publications:

        report += f"## {pub['title']}\n"
        report += f"- Fecha: {pub['publication_date']}\n"
        report += f"- Dominio: {pub['primary_domain']}\n"
        report += f"- Módulo Impactado: {pub['impacted_module']}\n"
        report += f"- Severidad: {pub['severity']}\n"
        report += f"- Motivo: {pub['impact_reason']}\n\n"

    return report
