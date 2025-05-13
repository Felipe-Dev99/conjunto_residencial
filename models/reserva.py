from app import db
from datetime import datetime, time


class Estado_reserva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False)



class Reserva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    id_espacio_reserva = db.Column(db.Integer, db.ForeignKey('espacios_reserva.id'), nullable=False)
    numero_radicado = db.Column(db.String(25), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    horario = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.String(300), nullable=False)
    id_estado = db.Column(db.Integer, db.ForeignKey('estado_reserva.id'), nullable=False, default=1)
    comprobante_pago = db.Column(db.String(255))
    comprobante_pago1 = db.Column(db.LargeBinary)  # Guarda los bytes del archivo
    comprobante_mimetype = db.Column(db.String(100)) 
    comprobante_path = db.Column(db.String(255))  # Guarda la ruta del archivo
    id_factura = db.Column(db.Integer)
    observacion = db.Column(db.String(255))
    
    usuario = db.relationship("Usuarios", backref="solicitudes")
    estado = db.relationship("Estado_reserva", backref="solicitudes")
    espacios = db.relationship("Espacios_reserva", backref="espacios")
    facturas = db.relationship('Facturas', backref='reserva', cascade="all, delete-orphan")

class Facturas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_solicitud = db.Column(db.Integer, db.ForeignKey('reserva.id'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha_emision = db.Column(db.Date, default=datetime)
    comprobante_pago = db.Column(db.String(255))

    solicitud = db.relationship("Reserva", backref="factura")
    usuario = db.relationship("Usuarios", backref="facturas")


class Espacios_reserva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)
    valor = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.Boolean, default=True)  # Activo o Inactivo



@staticmethod
def generar_numero_radicado_reserva():
    """Genera un número de radicado basado en el año y un número secuencial"""
    año_actual = datetime.now().year
    ultima_pqrs = Reserva.query.filter(Reserva.numero_radicado.like(f"Re-{año_actual}-%")).order_by(Reserva.id.desc()).first()

    if ultima_pqrs:
        ultimo_numero = int(ultima_pqrs.numero_radicado.split("-")[2])
    else:
        ultimo_numero = 0

    nuevo_numero = f"Re-{año_actual}-{str(ultimo_numero + 1).zfill(5)}"
    return nuevo_numero