"""
Flask dashboard para el sistema de monitoreo regulatorio.

Fase 10: Hardening para produccion.
- Secret key desde variable de entorno
- Autenticacion basica en endpoints admin (ADMIN_TOKEN)
- Health check endpoint (/health)
- Security headers (X-Frame, X-XSS, etc.)
- Error handlers (404, 500)
"""

import os
import sys
import threading
import logging
import secrets
from functools import wraps
from datetime import datetime

# Asegurar que el directorio raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify,
)

from web.db_queries import (
    get_summary_stats,
    get_filtered_publications,
    get_publication_by_id,
    get_pipeline_counts,
)

logger = logging.getLogger(__name__)

# Estado del pipeline (simple, para uso interno single-process)
_pipeline_state = {
    "running": False,
    "last_action": None,
    "last_error": None,
}

# =====================
# AUTENTICACION ADMIN
# =====================
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()


def _check_admin_auth():
    """Verifica autenticacion para endpoints admin.

    Metodos soportados:
    1. Header: Authorization: Bearer <ADMIN_TOKEN>
    2. Query param: ?token=<ADMIN_TOKEN>
    3. Form data: token=<ADMIN_TOKEN>
    4. Si ADMIN_TOKEN no esta configurado, permitir (desarrollo local).
    """
    if not ADMIN_TOKEN:
        return True  # Sin token configurado = desarrollo local

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == ADMIN_TOKEN:
        return True

    if request.args.get("token") == ADMIN_TOKEN:
        return True

    if request.form.get("token") == ADMIN_TOKEN:
        return True

    return False


def admin_required(f):
    """Decorator para proteger endpoints admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _check_admin_auth():
            logger.warning("Acceso no autorizado a %s desde %s",
                           request.path, request.remote_addr)
            if request.path.startswith("/api/"):
                return jsonify({"error": "No autorizado"}), 401
            flash("Acceso no autorizado.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    # Secret key desde variable de entorno (con fallback seguro para dev)
    app.secret_key = os.environ.get(
        "FLASK_SECRET_KEY",
        secrets.token_hex(32),
    )

    # =====================
    # SECURITY HEADERS
    # =====================
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # =====================
    # ERROR HANDLERS
    # =====================
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Recurso no encontrado"}), 404
        flash("Pagina no encontrada.", "danger")
        return redirect(url_for("index"))

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Error interno del servidor")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno del servidor"}), 500
        flash("Error interno del servidor. Intente de nuevo.", "danger")
        return redirect(url_for("index"))

    # =====================
    # HEALTH CHECK
    # =====================
    @app.route("/health")
    def health_check():
        """Endpoint de health check para Railway / load balancers."""
        try:
            from database.db import get_connection
            conn = get_connection()
            conn.execute("SELECT 1")
            conn.close()
            db_ok = True
        except Exception:
            db_ok = False

        status = "healthy" if db_ok else "degraded"
        code = 200 if db_ok else 503

        return jsonify({
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "database": "ok" if db_ok else "error",
            "version": "1.0.0",
        }), code

    # =====================
    # RESUMEN (index)
    # =====================
    @app.route("/")
    def index():
        try:
            stats = get_summary_stats()
        except Exception:
            logger.exception("Error obteniendo estadisticas")
            stats = {}
        return render_template("index.html", stats=stats)

    # =====================
    # PUBLICACIONES (tabla)
    # =====================
    @app.route("/publicaciones")
    def publications_list():
        severity = request.args.get("severity", "")
        domain = request.args.get("domain", "")
        module = request.args.get("module", "")
        source = request.args.get("source", "")
        page = request.args.get("page", 1, type=int)
        sort_by = request.args.get("sort", "analyzed_at")
        sort_dir = request.args.get("dir", "DESC")

        try:
            pubs, total = get_filtered_publications(
                severity=severity or None,
                domain=domain or None,
                module=module or None,
                source=source or None,
                impact_only=True,
                page=page,
                per_page=25,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
        except Exception:
            logger.exception("Error obteniendo publicaciones")
            pubs, total = [], 0

        total_pages = max(1, (total + 24) // 25)

        filter_params = []
        if severity:
            filter_params.append(f"severity={severity}")
        if domain:
            filter_params.append(f"domain={domain}")
        if module:
            filter_params.append(f"module={module}")
        if source:
            filter_params.append(f"source={source}")
        filter_params.append(f"sort={sort_by}")
        filter_params.append(f"dir={sort_dir}")
        query_string = "&".join(filter_params)

        return render_template(
            "publications.html",
            publications=pubs,
            total=total,
            page=page,
            total_pages=total_pages,
            severity=severity,
            domain=domain,
            module=module,
            source=source,
            sort_by=sort_by,
            sort_dir=sort_dir,
            query_string=query_string,
        )

    # =====================
    # DETALLE
    # =====================
    @app.route("/publicaciones/<int:pub_id>")
    def publication_detail(pub_id):
        pub = get_publication_by_id(pub_id)
        if not pub:
            flash("Publicacion no encontrada.", "danger")
            return redirect(url_for("publications_list"))
        return render_template("detail.html", pub=pub)

    # =====================
    # PIPELINE (protegido)
    # =====================
    @app.route("/pipeline")
    def pipeline_status():
        counts = get_pipeline_counts()
        return render_template(
            "pipeline.html",
            counts=counts,
            pipeline_state=_pipeline_state,
        )

    @app.route("/pipeline/analizar", methods=["POST"])
    @admin_required
    def trigger_analysis():
        if _pipeline_state["running"]:
            flash("El pipeline ya esta en ejecucion. Espere a que termine.", "warning")
            return redirect(url_for("pipeline_status"))

        def _run():
            _pipeline_state["running"] = True
            _pipeline_state["last_error"] = None
            try:
                from main import run_content_pipeline, run_analysis_pipeline
                run_content_pipeline()
                run_analysis_pipeline()
                _pipeline_state["last_action"] = "Analisis completado exitosamente"
            except Exception as e:
                _pipeline_state["last_error"] = str(e)
                logger.exception("Error en pipeline de analisis")
            finally:
                _pipeline_state["running"] = False

        threading.Thread(target=_run, daemon=True).start()
        flash("Pipeline de analisis iniciado. Actualice la pagina para ver el progreso.", "info")
        return redirect(url_for("pipeline_status"))

    @app.route("/pipeline/reanalizar", methods=["POST"])
    @admin_required
    def trigger_reanalysis():
        if _pipeline_state["running"]:
            flash("El pipeline ya esta en ejecucion. Espere a que termine.", "warning")
            return redirect(url_for("pipeline_status"))

        def _run():
            _pipeline_state["running"] = True
            _pipeline_state["last_error"] = None
            try:
                from database.db import reset_all_analyzed
                from main import run_analysis_pipeline
                affected = reset_all_analyzed()
                _pipeline_state["last_action"] = f"Reset {affected} publicaciones"
                run_analysis_pipeline()
                _pipeline_state["last_action"] = "Re-analisis completado exitosamente"
            except Exception as e:
                _pipeline_state["last_error"] = str(e)
                logger.exception("Error en re-analisis")
            finally:
                _pipeline_state["running"] = False

        threading.Thread(target=_run, daemon=True).start()
        flash("Re-analisis iniciado. Actualice la pagina para ver el progreso.", "info")
        return redirect(url_for("pipeline_status"))

    # =====================
    # API JSON
    # =====================
    @app.route("/api/stats")
    def api_stats():
        try:
            stats = get_summary_stats()
            stats["pipeline_running"] = _pipeline_state["running"]
            stats["last_action"] = _pipeline_state["last_action"]
            stats["last_error"] = _pipeline_state["last_error"]
            return jsonify(stats)
        except Exception:
            logger.exception("Error en /api/stats")
            return jsonify({"error": "Error obteniendo estadisticas"}), 500

    # =====================
    # WEBHOOK TEST (protegido)
    # =====================
    @app.route("/api/webhook/test", methods=["POST"])
    @admin_required
    def test_webhook():
        """Envia un webhook de prueba con las publicaciones actuales con impacto."""
        from database.db import get_impact_publications
        from notifications.webhook import send_webhook

        impact_pubs = get_impact_publications()
        if not impact_pubs:
            return jsonify({"error": "No hay publicaciones con impacto"}), 404

        impact_dicts = [dict(row) for row in impact_pubs]
        success = send_webhook(impact_dicts, {"test": True})

        if success:
            return jsonify({"status": "ok", "sent": len(impact_dicts)})
        else:
            return jsonify({"error": "Webhook no configurado o fallo"}), 500

    return app
