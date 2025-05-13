from app import db

class Roles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False)
    permisos = db.relationship('Permisos', secondary='rol_permiso', backref='roles')

class Permisos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    tipo = db.Column(db.String(45), nullable=False)

class RolPermiso(db.Model):
    __tablename__ = "rol_permiso"
    #id = db.Column(db.Integer, primary_key=True)
    rol_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, primary_key=True)
    permiso_id = db.Column(db.Integer, db.ForeignKey("permisos.id"), nullable=False, primary_key=True)

