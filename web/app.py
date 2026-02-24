"""
Flask dashboard para el sistema de monitoreo regulatorio.
"""

import os
import sys
import threading
import logging

# Asegurar que el directorio raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify
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


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = "regulatory-dashboard-internal-2026"

    # =====================
    # RESUMEN (index)
    # =====================
    @app.route("/")
    def index():
        stats = get_summary_stats()
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

        total_pages = max(1, (total + 24) // 25)

        # Construir query params para paginacion (sin page)
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
    # PIPELINE
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
        stats = get_summary_stats()
        stats["pipeline_running"] = _pipeline_state["running"]
        stats["last_action"] = _pipeline_state["last_action"]
        stats["last_error"] = _pipeline_state["last_error"]
        return jsonify(stats)

    return app
