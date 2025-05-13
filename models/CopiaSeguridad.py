from app import db

class CopiaSeguridad(db.Model):
    __tablename__ = 'copias_seguridad'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False)
    ruta_archivo = db.Column(db.String(255), nullable=False)
    tamaño = db.Column(db.Integer)
    estado = db.Column(db.String(20), default='Exitoso')
