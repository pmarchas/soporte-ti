from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default="usuario")  # "usuario" o "admin"
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship("Ticket", backref="autor", lazy=True)
    comentarios = db.relationship("Comentario", backref="autor", lazy=True)


class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    prioridad = db.Column(db.String(20), default="Media")  # Alta, Media, Baja
    estado = db.Column(db.String(30), default="Abierto")   # Abierto, En progreso, Resuelto, Cerrado
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comentarios = db.relationship("Comentario", backref="ticket", lazy=True, cascade="all, delete-orphan")


class Comentario(db.Model):
    __tablename__ = "comentarios"
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.Text, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
