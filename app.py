from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from collections import defaultdict
from models import db, User, Ticket, Comentario
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "SQLALCHEMY_DATABASE_URI", "sqlite:///tickets.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Configuración de correo (vía variables de entorno) ──────────────────────
MAIL_SERVER   = os.environ.get("MAIL_SERVER", "")
MAIL_PORT     = int(os.environ.get("MAIL_PORT", 587))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
MAIL_USE_TLS  = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
ADMIN_EMAIL   = os.environ.get("ADMIN_EMAIL", "")   # destinatario de nuevos tickets
APP_URL       = os.environ.get("APP_URL", "http://localhost:5000")

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ──────────────────────────────────────────────
# EMAIL
# ──────────────────────────────────────────────

def _enviar_correo(destinatario, asunto, html):
    """Envía un correo en un hilo separado para no bloquear la respuesta."""
    if not all([MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, destinatario]):
        return  # Email no configurado, se omite silenciosamente

    def _enviar():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"]    = MAIL_USERNAME
            msg["To"]      = destinatario
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
                if MAIL_USE_TLS:
                    server.starttls()
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.sendmail(MAIL_USERNAME, destinatario, msg.as_string())
        except Exception as e:
            app.logger.error(f"Error al enviar correo: {e}")

    threading.Thread(target=_enviar, daemon=True).start()


def notificar_nuevo_ticket(ticket):
    """Avisa al equipo de sistemas de un ticket reciente."""
    enlace = f"{APP_URL}/ticket/{ticket.id}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a">
      <h2 style="font-size:1.1rem;margin-bottom:.5rem">
        🎫 Nuevo ticket: <em>{ticket.titulo}</em>
      </h2>
      <p style="margin:.25rem 0"><strong>Prioridad:</strong> {ticket.prioridad}</p>
      <p style="margin:.25rem 0"><strong>Usuario:</strong> {ticket.autor.nombre} ({ticket.autor.email})</p>
      <p style="margin:.25rem 0"><strong>Descripción:</strong></p>
      <p style="background:#f7f7f6;padding:.75rem;border-radius:6px;white-space:pre-wrap">{ticket.descripcion}</p>
      <a href="{enlace}"
         style="display:inline-block;margin-top:1rem;padding:.6rem 1.2rem;
                background:#2563eb;color:#fff;border-radius:6px;text-decoration:none;font-weight:600">
        Ver ticket #{ticket.id}
      </a>
      <p style="margin-top:1.5rem;font-size:.8rem;color:#888">Soporte TI · Notificación automática</p>
    </div>
    """
    _enviar_correo(ADMIN_EMAIL, f"[Soporte TI] Nuevo ticket #{ticket.id}: {ticket.titulo}", html)


def notificar_respuesta_admin(ticket, comentario, autor):
    """Avisa al usuario cuando el equipo de sistemas responde."""
    enlace = f"{APP_URL}/ticket/{ticket.id}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a">
      <h2 style="font-size:1.1rem;margin-bottom:.5rem">
        💬 El equipo de sistemas ha respondido a tu ticket
      </h2>
      <p style="margin:.25rem 0"><strong>Ticket:</strong> #{ticket.id} — {ticket.titulo}</p>
      <p style="margin:.5rem 0"><strong>Respuesta:</strong></p>
      <p style="background:#eff6ff;padding:.75rem;border-radius:6px;white-space:pre-wrap;
                border-left:3px solid #2563eb">{comentario.contenido}</p>
      <a href="{enlace}"
         style="display:inline-block;margin-top:1rem;padding:.6rem 1.2rem;
                background:#2563eb;color:#fff;border-radius:6px;text-decoration:none;font-weight:600">
        Ver conversación
      </a>
      <p style="margin-top:1.5rem;font-size:.8rem;color:#888">Soporte TI · Notificación automática</p>
    </div>
    """
    _enviar_correo(ticket.autor.email, f"[Soporte TI] Respuesta a tu ticket #{ticket.id}", html)


def notificar_cambio_estado(ticket):
    """Avisa al usuario cuando cambia el estado de su ticket."""
    enlace = f"{APP_URL}/ticket/{ticket.id}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a">
      <h2 style="font-size:1.1rem;margin-bottom:.5rem">
        🔄 Tu ticket ha sido actualizado
      </h2>
      <p style="margin:.25rem 0"><strong>Ticket:</strong> #{ticket.id} — {ticket.titulo}</p>
      <p style="margin:.25rem 0"><strong>Nuevo estado:</strong> {ticket.estado}</p>
      <a href="{enlace}"
         style="display:inline-block;margin-top:1rem;padding:.6rem 1.2rem;
                background:#2563eb;color:#fff;border-radius:6px;text-decoration:none;font-weight:600">
        Ver ticket
      </a>
      <p style="margin-top:1.5rem;font-size:.8rem;color:#888">Soporte TI · Notificación automática</p>
    </div>
    """
    _enviar_correo(ticket.autor.email, f"[Soporte TI] Estado actualizado: ticket #{ticket.id}", html)


# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        nombre   = request.form.get("nombre", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")

        if not nombre or not email or not password:
            flash("Todos los campos son obligatorios.", "error")
        elif password != confirmar:
            flash("Las contraseñas no coinciden.", "error")
        elif len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Ya existe una cuenta con ese correo.", "error")
        else:
            user = User(nombre=nombre, email=email,
                        password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("login"))

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ──────────────────────────────────────────────
# DASHBOARD USUARIO
# ──────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.rol == "admin":
        return redirect(url_for("admin_panel"))
    tickets = Ticket.query.filter_by(usuario_id=current_user.id)\
                          .order_by(Ticket.creado_en.desc()).all()
    return render_template("dashboard.html", tickets=tickets)


@app.route("/nuevo-ticket", methods=["GET", "POST"])
@login_required
def nuevo_ticket():
    if current_user.rol == "admin":
        abort(403)
    if request.method == "POST":
        titulo      = request.form.get("titulo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        prioridad   = request.form.get("prioridad", "Media")

        if not titulo or not descripcion:
            flash("El título y la descripción son obligatorios.", "error")
        elif prioridad not in ("Alta", "Media", "Baja"):
            flash("Prioridad no válida.", "error")
        else:
            ticket = Ticket(titulo=titulo, descripcion=descripcion,
                            prioridad=prioridad, usuario_id=current_user.id)
            db.session.add(ticket)
            db.session.commit()
            notificar_nuevo_ticket(ticket)
            flash("Ticket enviado correctamente.", "success")
            return redirect(url_for("dashboard"))

    return render_template("nuevo_ticket.html")


@app.route("/ticket/<int:ticket_id>")
@login_required
def ver_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if current_user.rol != "admin" and ticket.usuario_id != current_user.id:
        abort(403)
    comentarios = Comentario.query.filter_by(ticket_id=ticket.id)\
                                  .order_by(Comentario.creado_en.asc()).all()
    return render_template("ticket_detalle.html", ticket=ticket, comentarios=comentarios)


@app.route("/ticket/<int:ticket_id>/comentar", methods=["POST"])
@login_required
def comentar(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if current_user.rol != "admin" and ticket.usuario_id != current_user.id:
        abort(403)
    contenido = request.form.get("contenido", "").strip()
    if not contenido:
        flash("El comentario no puede estar vacío.", "error")
    else:
        comentario = Comentario(contenido=contenido,
                                ticket_id=ticket.id,
                                usuario_id=current_user.id)
        db.session.add(comentario)
        ticket.actualizado_en = datetime.utcnow()
        db.session.commit()
        # Notificar al usuario si responde el admin, o al admin si responde el usuario
        if current_user.rol == "admin":
            notificar_respuesta_admin(ticket, comentario, current_user)
        flash("Comentario añadido.", "success")
    return redirect(url_for("ver_ticket", ticket_id=ticket.id))


# ──────────────────────────────────────────────
# PANEL DE ADMINISTRACIÓN (EQUIPO DE SISTEMAS)
# ──────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin_panel():
    if current_user.rol != "admin":
        abort(403)

    estado_filtro   = request.args.get("estado", "")
    prioridad_filtro = request.args.get("prioridad", "")

    query = Ticket.query
    if estado_filtro:
        query = query.filter_by(estado=estado_filtro)
    if prioridad_filtro:
        query = query.filter_by(prioridad=prioridad_filtro)

    tickets = query.order_by(Ticket.creado_en.desc()).all()
    return render_template("admin_panel.html", tickets=tickets,
                           estado_filtro=estado_filtro,
                           prioridad_filtro=prioridad_filtro)


@app.route("/admin/estadisticas")
@login_required
def admin_estadisticas():
    if current_user.rol != "admin":
        abort(403)

    todos = Ticket.query.all()
    total = len(todos)

    # Conteo por estado
    por_estado = defaultdict(int)
    for t in todos:
        por_estado[t.estado] += 1

    # Conteo por prioridad
    por_prioridad = defaultdict(int)
    for t in todos:
        por_prioridad[t.prioridad] += 1

    # Tickets por día (últimos 30 días)
    hoy = datetime.utcnow().date()
    hace_30 = hoy - timedelta(days=29)
    conteo_diario = defaultdict(int)
    for t in todos:
        fecha = t.creado_en.date()
        if fecha >= hace_30:
            conteo_diario[str(fecha)] += 1

    dias = [(hace_30 + timedelta(days=i)) for i in range(30)]
    labels_diarios  = [d.strftime("%-d %b") for d in dias]
    valores_diarios = [conteo_diario.get(str(d), 0) for d in dias]

    # Tickets recientes (últimos 5)
    recientes = Ticket.query.order_by(Ticket.creado_en.desc()).limit(5).all()

    # Tiempo medio de resolución (tickets cerrados/resueltos con al menos un comentario)
    resueltos = [t for t in todos if t.estado in ("Resuelto", "Cerrado")]
    if resueltos:
        duraciones = []
        for t in resueltos:
            delta = (t.actualizado_en - t.creado_en).total_seconds() / 3600
            duraciones.append(delta)
        tiempo_medio_h = round(sum(duraciones) / len(duraciones), 1)
    else:
        tiempo_medio_h = None

    estados_orden     = ["Abierto", "En progreso", "Resuelto", "Cerrado"]
    prioridades_orden = ["Alta", "Media", "Baja"]

    return render_template(
        "admin_estadisticas.html",
        total=total,
        por_estado={e: por_estado.get(e, 0) for e in estados_orden},
        por_prioridad={p: por_prioridad.get(p, 0) for p in prioridades_orden},
        labels_diarios=labels_diarios,
        valores_diarios=valores_diarios,
        recientes=recientes,
        tiempo_medio_h=tiempo_medio_h,
        resueltos=len(resueltos),
    )


@app.route("/admin/ticket/<int:ticket_id>/estado", methods=["POST"])
@login_required
def cambiar_estado(ticket_id):
    if current_user.rol != "admin":
        abort(403)
    ticket = Ticket.query.get_or_404(ticket_id)
    nuevo_estado = request.form.get("estado")
    estados_validos = ("Abierto", "En progreso", "Resuelto", "Cerrado")
    if nuevo_estado in estados_validos:
        ticket.estado = nuevo_estado
        ticket.actualizado_en = datetime.utcnow()
        db.session.commit()
        notificar_cambio_estado(ticket)
        flash(f"Estado actualizado a «{nuevo_estado}».", "success")
    else:
        flash("Estado no válido.", "error")
    return redirect(url_for("ver_ticket", ticket_id=ticket.id))


@app.route("/admin/usuarios")
@login_required
def admin_usuarios():
    if current_user.rol != "admin":
        abort(403)
    usuarios = User.query.order_by(User.creado_en.desc()).all()
    return render_template("admin_usuarios.html", usuarios=usuarios)


@app.route("/admin/usuarios/<int:user_id>/rol", methods=["POST"])
@login_required
def cambiar_rol(user_id):
    if current_user.rol != "admin":
        abort(403)
    if user_id == current_user.id:
        flash("No puedes cambiar tu propio rol.", "error")
        return redirect(url_for+"admin_usuarios"))
    user = User.query.get_or_404(user_id)
    nuevo_rol = request.form.get("rol")
    if nuevo_rol in ("usuario", "admin"):
        user.rol = nuevo_rol
        db.session.commit()
        flash(f"Rol de {user.nombre} actualizado.", "success")
    return redirect(url_for+"admin_usuarios"))


# ──────────────────────────────────────────────
# INIT
# ──────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False)
