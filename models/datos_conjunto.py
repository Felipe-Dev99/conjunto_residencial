from app import db

class DatosConjunto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    nit = db.Column(db.String(20), unique=True, nullable=False)
    numero_cuenta = db.Column(db.String(50), nullable=False)
    codigo_cuenta = db.Column(db.String(20), nullable=False)
    terminos_pdf = db.Column(db.String(100))
    politicas_pdf = db.Column(db.String(100))
