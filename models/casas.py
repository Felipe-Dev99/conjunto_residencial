from app import db

#class Casas(db.Model):
 #   id = db.Column(db.Integer, primary_key=True)
  #  torre = db.Column(db.String(20), nullable=False)
    #apartamento = db.Column(db.String(20), nullable=False)
    #usuarios = db.relationship('Usuarios', backref='casas', lazy=True)

class Torre(db.Model):
    __tablename__ = 'torre'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    #casas = db.relationship("Casas", backref="torre", cascade="all, delete-orphan")

class Apartamento(db.Model):
    __tablename__ = 'apartamento'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    #casas = db.relationship("Casas", backref="apartamento", cascade="all, delete-orphan")

class Casas(db.Model):
    __tablename__ = 'casas'
    id = db.Column(db.Integer, primary_key=True)
    id_torre = db.Column(db.Integer, db.ForeignKey("torre.id"), nullable=False)
    id_apartamento = db.Column(db.Integer, db.ForeignKey("apartamento.id"), nullable=False)

    torre = db.relationship("Torre", backref="casas_ref")
    apartamento = db.relationship("Apartamento", backref="casas_ref")
   