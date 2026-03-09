"""
Modulo de autenticacion con Flask-Login.

Roles:
- admin: acceso completo (dashboard, pipeline, gestion de usuarios)
- viewer: solo lectura del dashboard (publicaciones, resumen)
"""

import logging
import os
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database.connection import get_connection, adapt_sql, is_postgres

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()


# =====================
# USER MODEL
# =====================

class User(UserMixin):
    """Modelo de usuario para Flask-Login."""

    def __init__(self, id, email, password_hash, role="viewer", name=None, active=True):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.name = name or email.split("@")[0]
        self.active = active

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.role == "admin"

    @staticmethod
    def get_by_id(user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(adapt_sql("SELECT * FROM users WHERE id = ?"), (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            row = dict(row)
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                role=row["role"],
                name=row["name"],
                active=row["active"],
            )
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(adapt_sql("SELECT * FROM users WHERE email = ?"), (email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            row = dict(row)
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                role=row["role"],
                name=row["name"],
                active=row["active"],
            )
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))


# =====================
# DECORADORES
# =====================

def admin_required(f):
    """Decorator que requiere rol admin."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Acceso restringido a administradores.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# =====================
# RUTAS
# =====================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.get_by_email(email)

        if user and user.active and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            logger.info("Login exitoso: %s [%s]", email, user.role)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))

        logger.warning("Login fallido para: %s desde %s", email, request.remote_addr)
        flash("Email o contrasena incorrectos.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logger.info("Logout: %s", current_user.email)
    logout_user()
    flash("Sesion cerrada.", "info")
    return redirect(url_for("auth.login"))


# =====================
# GESTION DE USUARIOS
# =====================

def get_all_users():
    """Obtiene todos los usuarios."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, role, name, active, created_at FROM users ORDER BY id")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def create_user(email, password, role="viewer", name=None):
    """Crea un nuevo usuario."""
    password_hash = generate_password_hash(password)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            adapt_sql(
                "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, ?, ?)"
            ),
            (email.lower(), password_hash, role, name),
        )
        conn.commit()
        logger.info("Usuario creado: %s [%s]", email, role)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error creando usuario %s: %s", email, e)
        return False
    finally:
        conn.close()


def toggle_user_active(user_id):
    """Activa/desactiva un usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute(
            "UPDATE users SET active = NOT active WHERE id = %s RETURNING active",
            (user_id,),
        )
    else:
        cursor.execute(
            "UPDATE users SET active = CASE WHEN active THEN 0 ELSE 1 END WHERE id = ?",
            (user_id,),
        )
    conn.commit()
    conn.close()


def update_user(user_id, email=None, name=None, role=None):
    """Actualiza los campos de un usuario (email, nombre, rol)."""
    fields = []
    values = []
    if email is not None:
        fields.append("email = ?")
        values.append(email.lower())
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if not fields:
        return False
    values.append(user_id)
    sql = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(adapt_sql(sql), tuple(values))
        conn.commit()
        logger.info("Usuario id=%s actualizado: %s", user_id, ", ".join(fields))
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error actualizando usuario id=%s: %s", user_id, e)
        return False
    finally:
        conn.close()


def change_user_password(user_id, new_password):
    """Cambia la contrasena de un usuario."""
    password_hash = generate_password_hash(new_password)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            adapt_sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (password_hash, user_id),
        )
        conn.commit()
        logger.info("Contrasena actualizada para user_id=%s", user_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error cambiando contrasena user_id=%s: %s", user_id, e)
        return False
    finally:
        conn.close()


def create_initial_admin():
    """Crea el usuario admin inicial desde variables de entorno.

    Variables:
        ADMIN_EMAIL: email del admin
        ADMIN_PASSWORD: contrasena del admin

    Solo crea si no existe ya un admin con ese email.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if not admin_email or not admin_password:
        logger.debug("ADMIN_EMAIL o ADMIN_PASSWORD no configurados. Sin admin inicial.")
        return

    existing = User.get_by_email(admin_email)
    if existing:
        logger.debug("Admin ya existe: %s", admin_email)
        return

    create_user(admin_email, admin_password, role="admin", name="Administrador")
    logger.info("Admin inicial creado: %s", admin_email)


def ensure_users_table():
    """Asegura que la tabla users existe (SQLite y PostgreSQL)."""
    conn = get_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                name TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                name TEXT,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()
