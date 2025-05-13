from app import db
from datetime import datetime

class LogActividad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    accion = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(255))
    fecha = db.Column(db.DateTime, default=datetime.now)
    ip = db.Column(db.String(45), nullable=False)

    usuario = db.relationship('Usuarios', backref='logs')
