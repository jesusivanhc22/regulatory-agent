"""
Flask dashboard para el sistema de monitoreo regulatorio.

Fase 11: PostgreSQL + Autenticacion con Flask-Login.
- Soporte dual SQLite/PostgreSQL via DATABASE_URL
- Login con roles Admin/Viewer
- Gestion de usuarios (admin)
- Health check endpoint (/health)
- Security headers
"""

import json
import os
import sys
import threading
import logging
import secrets
from datetime import datetime

# Asegurar que el directorio raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify,
)
from flask_login import login_required, current_user

from web.db_queries import (
    get_summary_stats,
    get_filtered_publications,
    get_publication_by_id,
    get_pipeline_counts,
)
from web.auth import (
    auth_bp,
    login_manager,
    admin_required,
    ensure_users_table,
    create_initial_admin,
    get_all_users,
    create_user,
    toggle_user_active,
    change_user_password,
    update_user,
)
from web.alerts import (
    ensure_alert_config_table,
    get_alert_config,
    save_alert_config,
)

logger = logging.getLogger(__name__)


def _log_db_health():
    """Log el estado de la BD al iniciar para diagnosticar perdida de datos."""
    try:
        from database.connection import get_connection, is_postgres
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        row = cursor.fetchone()
        user_count = dict(row)["cnt"] if hasattr(row, "keys") else row[0]
        cursor.execute("SELECT COUNT(*) as cnt FROM publications")
        row = cursor.fetchone()
        pub_count = dict(row)["cnt"] if hasattr(row, "keys") else row[0]
        cursor.execute("SELECT COUNT(*) as cnt FROM publications WHERE impact_flag = 1")
        row = cursor.fetchone()
        impact_count = dict(row)["cnt"] if hasattr(row, "keys") else row[0]
        conn.close()

        logger.info("=== DB HEALTH CHECK (startup) ===")
        logger.info("Backend: %s", "PostgreSQL" if is_postgres() else "SQLite")
        logger.info("Usuarios: %d | Publicaciones: %d | Con impacto: %d",
                     user_count, pub_count, impact_count)
        logger.info("=================================")

        if user_count == 0:
            logger.warning("BD SIN USUARIOS - Posible recreacion de la BD en deploy.")
    except Exception as e:
        logger.error("Error en DB health check: %s", e)


# Estado del pipeline (simple, para uso interno single-process)
_pipeline_state = {
    "running": False,
    "last_action": None,
    "last_error": None,
}


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
    # FLASK-LOGIN
    # =====================
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicie sesion para acceder."
    login_manager.login_message_category = "info"

    app.register_blueprint(auth_bp)

    # Crear tablas y admin inicial
    with app.app_context():
        ensure_users_table()
        ensure_alert_config_table()
        create_initial_admin()
        _log_db_health()

    # Filtro Jinja para parsear JSON (usado en templates para ai_actions)
    @app.template_filter("from_json")
    def from_json_filter(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []

    # Filtro Jinja para separador de miles (ej. 2066 → "2,066")
    @app.template_filter("comma")
    def comma_filter(value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return value

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
    # HEALTH CHECK (publico)
    # =====================
    @app.route("/health")
    def health_check():
        """Endpoint de health check para Railway / load balancers."""
        user_count = 0
        pub_count = 0
        impact_count = 0
        try:
            from database.connection import get_connection, is_postgres
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM users")
            row = cur.fetchone()
            user_count = dict(row)["cnt"] if hasattr(row, "keys") else row[0]
            cur.execute("SELECT COUNT(*) as cnt FROM publications")
            row = cur.fetchone()
            pub_count = dict(row)["cnt"] if hasattr(row, "keys") else row[0]
            cur.execute("SELECT COUNT(*) as cnt FROM publications WHERE impact_flag = 1")
            row = cur.fetchone()
            impact_count = dict(row)["cnt"] if hasattr(row, "keys") else row[0]
            backend = "postgres" if is_postgres() else "sqlite"
            conn.close()
            db_ok = True
        except Exception:
            db_ok = False
            backend = "unknown"

        status = "healthy" if db_ok else "degraded"
        code = 200 if db_ok else 503

        return jsonify({
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "database": backend if db_ok else "error",
            "users": user_count,
            "publications": pub_count,
            "impact_publications": impact_count,
            "version": "2.1.0",
        }), code

    # =====================
    # RESUMEN (index)
    # =====================
    @app.route("/")
    @login_required
    def index():
        try:
            stats = get_summary_stats()
        except Exception:
            logger.exception("Error obteniendo estadisticas")
            stats = {}

        # Publicaciones con impacto para tabla inline
        try:
            impact_pubs, impact_total = get_filtered_publications(
                impact_only=True,
                page=1,
                per_page=100,
                sort_by="analyzed_at",
                sort_dir="DESC",
            )
        except Exception:
            logger.exception("Error obteniendo publicaciones con impacto")
            impact_pubs, impact_total = [], 0

        return render_template(
            "index.html",
            stats=stats,
            publications=impact_pubs,
            impact_total=impact_total,
        )

    # =====================
    # PUBLICACIONES (tabla)
    # =====================
    @app.route("/publicaciones")
    @login_required
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
    @login_required
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
    @login_required
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
    # GESTION DE USUARIOS
    # =====================
    @app.route("/usuarios")
    @admin_required
    def users_list():
        users = get_all_users()
        return render_template("users.html", users=users)

    @app.route("/usuarios/crear", methods=["POST"])
    @admin_required
    def users_create():
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "viewer")
        name = request.form.get("name", "").strip()

        if not email or not password:
            flash("Email y contrasena son obligatorios.", "danger")
            return redirect(url_for("users_list"))

        if role not in ("admin", "viewer"):
            role = "viewer"

        if create_user(email, password, role=role, name=name or None):
            flash(f"Usuario {email} creado como {role}.", "success")
        else:
            flash("Error creando usuario. Verifique que el email no exista.", "danger")

        return redirect(url_for("users_list"))

    @app.route("/usuarios/<int:user_id>/editar", methods=["POST"])
    @admin_required
    def users_edit(user_id):
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()

        if not email:
            flash("El email es obligatorio.", "danger")
            return redirect(url_for("users_list"))

        if role not in ("admin", "viewer"):
            role = "viewer"

        # No permitir quitarse el propio rol admin
        if user_id == current_user.id and role != "admin":
            flash("No puede cambiar su propio rol de administrador.", "warning")
            return redirect(url_for("users_list"))

        if update_user(user_id, email=email, name=name or None, role=role):
            flash(f"Usuario {email} actualizado.", "success")
        else:
            flash("Error actualizando usuario. Verifique que el email no exista.", "danger")
        return redirect(url_for("users_list"))

    @app.route("/usuarios/<int:user_id>/toggle", methods=["POST"])
    @admin_required
    def users_toggle(user_id):
        if user_id == current_user.id:
            flash("No puede desactivar su propia cuenta.", "warning")
            return redirect(url_for("users_list"))
        toggle_user_active(user_id)
        flash("Estado del usuario actualizado.", "info")
        return redirect(url_for("users_list"))

    @app.route("/usuarios/<int:user_id>/password", methods=["POST"])
    @admin_required
    def users_change_password(user_id):
        new_password = request.form.get("new_password", "").strip()
        if not new_password or len(new_password) < 6:
            flash("La contrasena debe tener al menos 6 caracteres.", "danger")
            return redirect(url_for("users_list"))

        if change_user_password(user_id, new_password):
            flash("Contrasena actualizada exitosamente.", "success")
        else:
            flash("Error actualizando contrasena.", "danger")
        return redirect(url_for("users_list"))

    # =====================
    # ALERTAS (config)
    # =====================
    @app.route("/alertas")
    @admin_required
    def alerts_config():
        users = get_all_users()
        config = get_alert_config()
        webhook_url = os.environ.get("WEBHOOK_URL", "")
        return render_template(
            "alertas.html",
            users=users,
            config=config,
            webhook_url=webhook_url,
        )

    @app.route("/alertas/guardar", methods=["POST"])
    @admin_required
    def alerts_save():
        recipients = request.form.getlist("recipients")
        schedule_day = request.form.get("schedule_day", "monday")
        schedule_hour = request.form.get("schedule_hour", "9")

        if schedule_day not in (
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ):
            schedule_day = "monday"

        try:
            schedule_hour = str(int(schedule_hour) % 24)
        except (ValueError, TypeError):
            schedule_hour = "9"

        save_alert_config(recipients, schedule_day, schedule_hour)
        flash("Configuracion de alertas actualizada.", "success")
        return redirect(url_for("alerts_config"))

    # =====================
    # API JSON
    # =====================
    @app.route("/api/stats")
    @login_required
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
    # WEBHOOK TEST (admin)
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
