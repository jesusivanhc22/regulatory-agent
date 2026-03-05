"""
Sistema de notificaciones por webhook.

Cuando el pipeline detecta nuevas publicaciones con impacto,
dispara un POST al webhook configurado con los datos del evento.

El receptor (Zapier, Make, n8n, API propia, etc.) se encarga de
generar los correos a los usuarios.

Configuración via .env:
    WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/xxx/yyy
    WEBHOOK_SECRET=mi-secreto-compartido  (opcional, para validar origen)
"""

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


def _get_webhook_config():
    """Lee configuración de webhook desde variables de entorno."""
    url = os.environ.get("WEBHOOK_URL", "").strip()
    secret = os.environ.get("WEBHOOK_SECRET", "").strip()
    return url, secret


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Genera HMAC-SHA256 del payload para verificación en el receptor."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def _build_payload(new_publications: list, pipeline_stats: dict = None) -> dict:
    """
    Construye el payload del webhook.

    Args:
        new_publications: Lista de dicts con datos de publicaciones nuevas con impacto.
        pipeline_stats: Estadísticas opcionales del pipeline (total scrapeado, etc.)

    Returns:
        dict con la estructura del evento.
    """
    # Ordenar: ALTA primero, luego MEDIA
    severity_order = {"ALTA": 0, "MEDIA": 1}
    sorted_pubs = sorted(
        new_publications,
        key=lambda p: severity_order.get(p.get("severity", ""), 99),
    )

    publications_data = []
    for pub in sorted_pubs:
        pub_data = {
            "id": pub.get("id"),
            "title": pub.get("title", ""),
            "url": pub.get("url", ""),
            "source": pub.get("source", "DOF"),
            "severity": pub.get("severity", ""),
            "primary_domain": pub.get("primary_domain", ""),
            "impacted_module": pub.get("impacted_module", ""),
            "impact_reason": pub.get("impact_reason", ""),
            "publication_date": pub.get("publication_date"),
            "effective_date": pub.get("effective_date"),
        }
        # Campos de analisis IA (si existen)
        if pub.get("ai_summary"):
            pub_data["ai_summary"] = pub.get("ai_summary")
            pub_data["ai_actions"] = pub.get("ai_actions")
            pub_data["ai_deadline"] = pub.get("ai_deadline")
            pub_data["ai_priority"] = pub.get("ai_priority")
        publications_data.append(pub_data)

    alta_count = sum(1 for p in sorted_pubs if p.get("severity") == "ALTA")
    media_count = sum(1 for p in sorted_pubs if p.get("severity") == "MEDIA")

    # Generar HTML listo para email
    html_email = _build_html_email(publications_data, alta_count, media_count)

    # Subject line para el email
    if alta_count > 0:
        email_subject = f"Alerta Regulatoria: {alta_count} publicaciones ALTA y {media_count} MEDIA detectadas"
    else:
        email_subject = f"Monitor Regulatorio: {media_count} nuevas publicaciones MEDIA detectadas"

    return {
        "event": "new_impact_publications",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_new": len(publications_data),
            "alta": alta_count,
            "media": media_count,
        },
        "publications": publications_data,
        "pipeline_stats": pipeline_stats or {},
        "email_subject": email_subject,
        "html_email": html_email,
    }


def _build_html_email(publications: list, alta_count: int, media_count: int) -> str:
    """Genera el HTML del email listo para enviar desde Make/Zapier."""

    dashboard_url = os.environ.get(
        "DASHBOARD_URL",
        "https://web-production-fdec2.up.railway.app",
    )

    MODULE_LABELS = {
        "INVOICING": "Facturacion",
        "TAX_REPORTING": "Reportes Fiscales",
        "INVENTORY": "Inventario",
        "ACCOUNTING": "Contabilidad",
        "POS": "Punto de Venta",
        "REGULATORY_COMPLIANCE": "Cumplimiento Regulatorio",
        "NONE": "-",
    }
    DOMAIN_LABELS = {
        "HEALTH": "Salud",
        "FISCAL": "Fiscal",
        "RETAIL": "Retail",
        "BORDER": "Frontera",
        "CURRENCY": "Moneda",
    }
    SOURCE_LABELS = {
        "DOF": "Diario Oficial de la Federacion",
        "SAT": "Servicio de Administracion Tributaria",
        "COFEPRIS": "COFEPRIS",
        "SE_SALUD": "Secretaria de Salud",
        "COFEPRIS_NORMAS": "COFEPRIS Marco Normativo",
    }

    # Separar ALTA y MEDIA
    alta_pubs = [p for p in publications if p.get("severity") == "ALTA"]
    media_pubs = [p for p in publications if p.get("severity") == "MEDIA"]

    def _pub_row(pub):
        title = pub.get("title", "")
        url = pub.get("url", "")
        source = pub.get("source", "DOF")
        module = MODULE_LABELS.get(pub.get("impacted_module", ""), pub.get("impacted_module", ""))
        domain = DOMAIN_LABELS.get(pub.get("primary_domain", ""), pub.get("primary_domain", ""))
        pub_date = pub.get("publication_date") or "-"
        eff_date = pub.get("effective_date")
        severity = pub.get("severity", "")

        sev_color = "#dc3545" if severity == "ALTA" else "#f0ad4e"
        sev_label = severity

        # Campos IA
        ai_summary = pub.get("ai_summary", "")
        ai_actions_raw = pub.get("ai_actions", "")
        ai_deadline = pub.get("ai_deadline", "")
        ai_priority = pub.get("ai_priority", "")

        eff_html = ""
        if eff_date:
            eff_html = f"""
            <tr>
                <td style="padding:2px 0;color:#555;font-size:13px;">Entrada en vigor:</td>
                <td style="padding:2px 0;font-size:13px;font-weight:bold;color:#dc3545;">{eff_date}</td>
            </tr>"""

        # Seccion de analisis IA
        ai_html = ""
        if ai_summary:
            # Badge de prioridad IA
            priority_colors = {
                "URGENTE": "#dc3545",
                "PLANIFICAR": "#f0ad4e",
                "INFORMATIVO": "#6c757d",
            }
            pri_color = priority_colors.get(ai_priority, "#6c757d")
            pri_badge = f"""<span style="display:inline-block;background:{pri_color};color:#fff;
                font-size:10px;font-weight:bold;padding:2px 8px;border-radius:3px;
                margin-bottom:6px;">{ai_priority}</span>""" if ai_priority else ""

            # Resumen
            ai_html += f"""
                    <tr>
                        <td style="padding-top:10px;">
                            {pri_badge}
                            <p style="margin:4px 0 0;font-size:13px;color:#333;line-height:1.5;
                                background:#f0f7ff;padding:8px 12px;border-radius:6px;
                                border-left:3px solid #1a73e8;">
                                {ai_summary}
                            </p>
                        </td>
                    </tr>"""

            # Acciones
            try:
                import json as _json
                actions = _json.loads(ai_actions_raw) if ai_actions_raw else []
            except (ValueError, TypeError):
                actions = []

            if actions:
                actions_items = "".join(
                    f'<li style="margin-bottom:3px;font-size:13px;color:#333;">{a}</li>'
                    for a in actions
                )
                ai_html += f"""
                    <tr>
                        <td style="padding-top:6px;">
                            <p style="margin:0 0 2px;font-size:12px;color:#555;font-weight:bold;">
                                Acciones recomendadas:
                            </p>
                            <ul style="margin:0;padding-left:20px;">{actions_items}</ul>
                        </td>
                    </tr>"""

            # Fecha limite IA
            if ai_deadline:
                ai_html += f"""
                    <tr>
                        <td style="padding-top:4px;">
                            <span style="font-size:12px;color:#dc3545;font-weight:bold;">
                                Fecha limite: {ai_deadline}
                            </span>
                        </td>
                    </tr>"""

        return f"""
        <tr>
            <td style="padding:16px 20px;border-bottom:1px solid #eee;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                        <td>
                            <span style="display:inline-block;background:{sev_color};color:#fff;font-size:11px;
                                font-weight:bold;padding:3px 10px;border-radius:3px;letter-spacing:0.5px;">
                                {sev_label}
                            </span>
                            <span style="display:inline-block;background:#e9ecef;color:#495057;font-size:11px;
                                padding:3px 8px;border-radius:3px;margin-left:6px;">
                                {domain}
                            </span>
                            <span style="display:inline-block;background:#e9ecef;color:#495057;font-size:11px;
                                padding:3px 8px;border-radius:3px;margin-left:4px;">
                                {module}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top:8px;">
                            <a href="{url}" style="color:#1a73e8;text-decoration:none;font-size:15px;
                                font-weight:600;line-height:1.4;">
                                {title}
                            </a>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top:6px;">
                            <table cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="padding:2px 0;color:#555;font-size:13px;">Fuente:</td>
                                    <td style="padding:2px 0 2px 8px;font-size:13px;">{SOURCE_LABELS.get(source, source)}</td>
                                </tr>
                                <tr>
                                    <td style="padding:2px 0;color:#555;font-size:13px;">Publicado:</td>
                                    <td style="padding:2px 0 2px 8px;font-size:13px;">{pub_date}</td>
                                </tr>{eff_html}
                            </table>
                        </td>
                    </tr>{ai_html}
                </table>
            </td>
        </tr>"""

    # Construir filas
    alta_rows = "".join(_pub_row(p) for p in alta_pubs)
    media_rows = "".join(_pub_row(p) for p in media_pubs)

    # Sección ALTA
    alta_section = ""
    if alta_pubs:
        alta_section = f"""
        <tr>
            <td style="padding:20px 20px 8px 20px;">
                <h2 style="margin:0;font-size:16px;color:#dc3545;border-bottom:2px solid #dc3545;
                    padding-bottom:6px;">
                    Severidad ALTA — Requiere atencion inmediata ({alta_count})
                </h2>
            </td>
        </tr>
        {alta_rows}"""

    # Sección MEDIA
    media_section = ""
    if media_pubs:
        media_section = f"""
        <tr>
            <td style="padding:20px 20px 8px 20px;">
                <h2 style="margin:0;font-size:16px;color:#856404;border-bottom:2px solid #f0ad4e;
                    padding-bottom:6px;">
                    Severidad MEDIA — Monitorear ({media_count})
                </h2>
            </td>
        </tr>
        {media_rows}"""

    today = datetime.utcnow().strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,Helvetica,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%"
    style="background:#f4f4f7;padding:20px 0;">
<tr><td align="center">
<table cellpadding="0" cellspacing="0" border="0" width="640"
    style="background:#ffffff;border-radius:8px;overflow:hidden;
    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

    <!-- Header -->
    <tr>
        <td style="background:#1a1a2e;padding:24px 20px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:700;
                letter-spacing:0.5px;">
                Monitor Regulatorio ERP Farmacias
            </h1>
            <p style="margin:6px 0 0;color:#a0a0b0;font-size:13px;">
                Reporte del {today}
            </p>
        </td>
    </tr>

    <!-- Resumen -->
    <tr>
        <td style="padding:20px;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td align="center" width="33%" style="padding:10px;">
                        <div style="background:#f8f9fa;border-radius:8px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:bold;color:#1a1a2e;">
                                {alta_count + media_count}
                            </div>
                            <div style="font-size:12px;color:#6c757d;margin-top:4px;">
                                NUEVAS
                            </div>
                        </div>
                    </td>
                    <td align="center" width="33%" style="padding:10px;">
                        <div style="background:#fdf0f0;border-radius:8px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:bold;color:#dc3545;">
                                {alta_count}
                            </div>
                            <div style="font-size:12px;color:#dc3545;margin-top:4px;">
                                ALTA
                            </div>
                        </div>
                    </td>
                    <td align="center" width="33%" style="padding:10px;">
                        <div style="background:#fff8e1;border-radius:8px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:bold;color:#f0ad4e;">
                                {media_count}
                            </div>
                            <div style="font-size:12px;color:#856404;margin-top:4px;">
                                MEDIA
                            </div>
                        </div>
                    </td>
                </tr>
            </table>
        </td>
    </tr>

    <!-- Publicaciones ALTA -->
    {alta_section}

    <!-- Publicaciones MEDIA -->
    {media_section}

    <!-- Footer -->
    <tr>
        <td style="padding:24px 20px;background:#f8f9fa;text-align:center;
            border-top:1px solid #eee;">
            <p style="margin:0;font-size:12px;color:#999;">
                Este correo fue generado automaticamente por el Monitor Regulatorio ERP Farmacias.
                <br>Para mas detalles, consulta el
                <a href="{dashboard_url}/publicaciones?impact=1"
                    style="color:#1a73e8;">dashboard completo</a>.
            </p>
        </td>
    </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_webhook(new_publications: list, pipeline_stats: dict = None) -> bool:
    """
    Envía webhook con las nuevas publicaciones con impacto.

    Solo se dispara si:
    1. WEBHOOK_URL está configurado
    2. Hay al menos 1 publicación nueva con impacto

    Args:
        new_publications: Lista de dicts (resultado de query SQL).
        pipeline_stats: Estadísticas del pipeline (opcional).

    Returns:
        True si se envió exitosamente, False si hubo error o no hay webhook.
    """
    url, secret = _get_webhook_config()

    if not url:
        logger.info("WEBHOOK_URL no configurado. Notificación omitida.")
        return False

    if not new_publications:
        logger.info("Sin publicaciones nuevas con impacto. Webhook omitido.")
        return False

    payload = _build_payload(new_publications, pipeline_stats)
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "RegMonitor-ERP/1.0",
        "X-Event": "new_impact_publications",
    }

    # Firmar payload si hay secreto configurado
    if secret:
        signature = _sign_payload(payload_bytes, secret)
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    # Enviar con reintentos
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                data=payload_bytes,
                headers=headers,
                timeout=30,
            )

            if response.status_code in (200, 201, 202, 204):
                logger.info(
                    "Webhook enviado: %d publicaciones nuevas con impacto (%d ALTA, %d MEDIA) -> %s",
                    payload["summary"]["total_new"],
                    payload["summary"]["alta"],
                    payload["summary"]["media"],
                    url[:50],
                )
                return True
            else:
                logger.warning(
                    "Webhook respondió %d (intento %d/%d): %s",
                    response.status_code, attempt, max_retries,
                    response.text[:200],
                )

        except requests.RequestException as e:
            logger.warning(
                "Error enviando webhook (intento %d/%d): %s",
                attempt, max_retries, str(e),
            )

        if attempt < max_retries:
            time.sleep(2 ** attempt)  # Backoff: 2s, 4s

    logger.error("Webhook falló después de %d intentos: %s", max_retries, url[:50])
    return False
