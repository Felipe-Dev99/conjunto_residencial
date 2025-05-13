from app import db
from datetime import datetime, time, timedelta

class PQRS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    numero_radicado = db.Column(db.String(25), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    tipo = db.Column(db.Integer, db.ForeignKey('descripcion_pqrs.id'), nullable=False)
    observacion = db.Column(db.Text, nullable=False)
    id_estado = db.Column(db.Integer, db.ForeignKey('estados_pqrs.id'), nullable=False)
    respuesta = db.Column(db.Text)
    fecha_respuesta = db.Column(db.DateTime)
    id_tipo = db.Column(db.Integer, db.ForeignKey('tipo_pqrs.id'), nullable=False)  # Cambio a tipo_pqrs.id
    fecha_max = db.Column(db.DateTime, nullable=True)
    archivo = db.Column(db.LargeBinary)
    nombre_archivo = db.Column(db.String(255))
    tipo_archivo = db.Column(db.String(50))
    id_asistente = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    usuario = db.relationship('Usuarios',foreign_keys=[id_usuario], backref='pqrs', lazy=True)
    estado = db.relationship('estados_pqrs', backref='pqrs', lazy=True)
    tipo_p = db.relationship('tipo_pqrs', backref='pqrs', lazy=True)  # Cambio a tipo_pqrs
    tipo_d = db.relationship('descripcion_pqrs', backref='pqrs', lazy=True)
    asistente = db.relationship('Usuarios', foreign_keys=[id_asistente], backref='pqrs_asignadas')  # Relación con el usuario (asistente)
    archivos = db.relationship('PQRSArchivo', backref='pqrs', lazy=True, cascade="all, delete-orphan")


class tipo_pqrs(db.Model):
    id = db.Column(db.Integer, primary_key=True)    
    nombre = db.Column(db.String(50), nullable=True,  unique=True) 

    #descripciones = db.relationship('descripcion_pqrs', backref='tipo_relacion', lazy=True)  # Relación con descripciones

class descripcion_pqrs(db.Model):
    id = db.Column(db.Integer, primary_key=True)    
    tipo = db.Column(db.String(100), nullable=True) 
    descripcion = db.Column(db.String(300), nullable=True) 
    id_tipo = db.Column(db.Integer, db.ForeignKey('tipo_pqrs.id'), nullable=False)

    tipo_pqrs = db.relationship('tipo_pqrs', backref=db.backref('descripciones', lazy=True))

class estados_pqrs(db.Model):
    id = db.Column(db.Integer, primary_key=True)    
    nombre = db.Column(db.String(50), nullable=True,  unique=True) 


class HistorialPQRS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_pqrs = db.Column(db.Integer, db.ForeignKey('pqrs.id'), nullable=False)
    respuesta = db.Column(db.Text, nullable=False)
    fecha_respuesta = db.Column(db.DateTime, default=datetime.utcnow)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete="SET NULL"), nullable=True)  # Permitir NULL
    estado_anterior = db.Column(db.String(50), nullable=False)
    estado_actual = db.Column(db.String(50), nullable=False)

    pqrs = db.relationship("PQRS", backref="historial")
    usuario = db.relationship("Usuarios", backref="respuestas")

# models.py
class PQRSArchivo(db.Model):
    __tablename__ = 'pqrs_archivos'
    id = db.Column(db.Integer, primary_key=True)
    id_pqrs = db.Column(db.Integer, db.ForeignKey('pqrs.id'), nullable=False)
    nombre_original = db.Column(db.String(255), nullable=False)
    nombre_encriptado = db.Column(db.String(255), nullable=False)


@staticmethod
def generar_numero_radicado():
    """Genera un número de radicado basado en el año y un número secuencial"""
    año_actual = datetime.now().year
    ultima_pqrs = PQRS.query.filter(PQRS.numero_radicado.like(f"PQRS-{año_actual}-%")).order_by(PQRS.id.desc()).first()

    if ultima_pqrs:
        ultimo_numero = int(ultima_pqrs.numero_radicado.split("-")[2])
    else:
        ultimo_numero = 0

    nuevo_numero = f"PQRS-{año_actual}-{str(ultimo_numero + 1).zfill(5)}"
    return nuevo_numero