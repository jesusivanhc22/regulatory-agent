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
        publications_data.append({
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
        })

    alta_count = sum(1 for p in sorted_pubs if p.get("severity") == "ALTA")
    media_count = sum(1 for p in sorted_pubs if p.get("severity") == "MEDIA")

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
    }


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
