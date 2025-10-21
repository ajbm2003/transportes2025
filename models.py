from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Vehiculo(db.Model):
    __tablename__ = 'vehiculos'
    id = db.Column(db.Integer, primary_key=True)
    ord = db.Column('ord', db.Integer, unique=True, nullable=False)
    marca = db.Column('marca', db.String(128))
    clase_tipo = db.Column('clase_tipo', db.String(128))
    ano = db.Column('ano', db.Integer)
    placas = db.Column('placas', db.String(64))
    color = db.Column('color', db.String(64))
    condicion = db.Column('condicion', db.String(64))
    estado = db.Column('estado', db.String(64))
    observacion = db.Column('observacion', db.String(512))
    matricula_2025 = db.Column('matricula_2025', db.String(64))
    division = db.Column('division', db.String(128))
    brigada = db.Column('brigada', db.String(128))
    unidad = db.Column('unidad', db.String(128))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'ORD': self.ord,
            'MARCA': self.marca or '',
            'CLASE / TIPO': self.clase_tipo or '',
            'ANO': self.ano or '',
            'PLACAS': self.placas or '',
            'COLOR': self.color or '',
            'CONDICION': self.condicion or '',
            'ESTADO': self.estado or '',
            'OBSERVACION': self.observacion or '',
            'MATRICULA 2025': self.matricula_2025 or '',
            'DIVISION': self.division or '',
            'BRIGADA': self.brigada or '',
            'UNIDAD': self.unidad or ''
        }
