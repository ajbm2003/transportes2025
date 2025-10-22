from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Vehiculo(db.Model):
    __tablename__ = 'vehiculos'
    id = db.Column(db.Integer, primary_key=True)
    ord = db.Column('ord', db.Integer, unique=True, nullable=False)
    clase_tipo = db.Column('clase_tipo', db.String(128))
    marca = db.Column('marca', db.String(128))
    modelo = db.Column('modelo', db.String(128))
    chasis = db.Column('chasis', db.String(128))
    motor = db.Column('motor', db.String(128))
    ano = db.Column('ano', db.String(128))  # Cambiado de Integer a String
    registro = db.Column('registro', db.String(128))
    placas = db.Column('placas', db.String(64))
    color = db.Column('color', db.String(64))
    tonelaje = db.Column('tonelaje', db.String(64))
    cilindraje = db.Column('cilindraje', db.String(64))
    combustible = db.Column('combustible', db.String(64))
    num_pasajeros = db.Column('num_pasajeros', db.String(64))  # Cambiado de Integer a String
    valor_esbye = db.Column('valor_esbye', db.String(128))
    valor_comercial = db.Column('valor_comercial', db.String(128))
    division = db.Column('division', db.String(128))
    brigada = db.Column('brigada', db.String(128))
    unidad = db.Column('unidad', db.String(128))
    necesidad_operacional_ft = db.Column('necesidad_operacional_ft', db.String(256))
    condicion = db.Column('condicion', db.String(64))
    estado = db.Column('estado', db.String(64))
    codigo_esbye = db.Column('codigo_esbye', db.String(128))
    eod = db.Column('eod', db.String(128))
    digito = db.Column('digito', db.String(64))
    matricula_2025 = db.Column('matricula_2025', db.String(64))
    custodio = db.Column('custodio', db.String(256))
    observacion = db.Column('observacion', db.String(512))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

  
    def to_dict(self):
        return {
            'ORD': self.ord,
            'CLASE / TIPO': self.clase_tipo or '',
            'MARCA': self.marca or '',
            'MODELO': self.modelo or '',
            'CHASIS': self.chasis or '',
            'MOTOR': self.motor or '',
            'ANO': self.ano or '',
            'REGISTRO': self.registro or '',
            'PLACAS': self.placas or '',
            'COLOR': self.color or '',
            'TONELAJE': self.tonelaje or '',
            'CILINDRAJE': self.cilindraje or '',
            'COMBUSTIBLE': self.combustible or '',
            '# PASAJ': self.num_pasajeros or '',
            'VALOR ESBYE': self.valor_esbye or '',
            'VALOR COMERCIAL': self.valor_comercial or '',
            'DIVISION': self.division or '',
            'BRIGADA': self.brigada or '',
            'UNIDAD': self.unidad or '',
            'NECESIDAD OPERACIONAL FT': self.necesidad_operacional_ft or '',
            'CONDICION': self.condicion or '',
            'ESTADO': self.estado or '',
            'CODIGO ESBYE': self.codigo_esbye or '',
            'EOD': self.eod or '',
            'DIGITO': self.digito or '',
            'MATRICULA 2025': self.matricula_2025 or '',
            'CUSTODIO': self.custodio or '',
            'OBSERVACION': self.observacion or ''
        }
