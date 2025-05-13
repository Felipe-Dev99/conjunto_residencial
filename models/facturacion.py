from app import db
from datetime import datetime, date


class Factura(db.Model):
    __tablename__ = 'factura'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    mes = db.Column(db.Integer, nullable=False)  # Mes de la factura (1-12)
    year = db.Column(db.Integer, nullable=False)  # Año de la factura
    fecha_emision = db.Column(db.Date, default=datetime.now, nullable=False)
    fecha_max_pago = db.Column(db.Date, nullable=False)  # Configurable según reglas de facturación
    valor_base = db.Column(db.Float, nullable=False)
    mora = db.Column(db.Float, nullable=False)
    descuento = db.Column(db.Float, nullable=False)
    saldo_anterior = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(50), default="Pendiente", nullable=False)
    validacion = db.Column(db.Float)
    fecha_subio_pago = db.Column(db.Date, nullable=False)
    abono = db.Column(db.Float, nullable=False)
    
    # Relación con Usuarios
    usuario_rel = db.relationship('Usuarios', backref="facturass")  # SOLO `backref`, SIN `back_populates`

    def __repr__(self):
        return f"<Factura {self.id} - Usuario {self.usuario_id} - Estado {self.estado}>"

class ConfiguracionFactura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tarifa = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    dia_habil_pago = db.Column(db.Integer, nullable=False, default=10)  # Ejemplo: día 10 de cada mes
    tasa_descuento = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)  # En porcentaje
    tasa_mora = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)  # En porcentaje


class HistoricoFacturacion(db.Model):
    __tablename__ = 'historico_facturacion'

    id = db.Column(db.Integer, primary_key=True)
    id_factura = db.Column(db.Integer, db.ForeignKey('factura.id'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto_pagado = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.now)
    tipo_pago = db.Column(db.Enum('Abono', 'Pago Total'), nullable=False)
    consecutivo_pago  = db.Column(db.String(25))
    estado = db.Column(db.String(50), default="Pendiente", nullable=False)
    comprobante_original = db.Column(db.String(255), nullable=True)
    comprobante_encriptado = db.Column(db.String(255), nullable=True)
    comprobante_path = db.Column(db.String(255), nullable=True)
    fecha_subio_pago = db.Column(db.Date, nullable=False)
    nota = db.Column(db.String(255))
    comprobacion = db.Column(db.Integer)

    factura = db.relationship('Factura', backref='pagos')
    usuario = db.relationship('Usuarios', backref='pagos_factura')


def generar_consecutivo_pago():
    ultimo_pago = HistoricoFacturacion.query.order_by(HistoricoFacturacion.id.desc()).first()
    if not ultimo_pago or not ultimo_pago.consecutivo_pago:
        return 'Fact-0001'
    
    ultimo_num = int(ultimo_pago.consecutivo_pago.split('-')[-1])
    nuevo_num = str(ultimo_num + 1).zfill(4)
    return f'Fact-{nuevo_num}'
