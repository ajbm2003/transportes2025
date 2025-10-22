import os
from urllib.parse import urlparse
from app import create_app
from utils import cargar_datos, limpiar_nans


def init_db(app):
    with app.app_context():
        print('Creando tablas...')

        # Importar modelos localmente para evitar ModuleNotFoundError si falta Flask-SQLAlchemy
        try:
            from models import db as models_db, Vehiculo as ModelVehiculo
        except Exception:
            models_db = None
            ModelVehiculo = None
            print('Aviso: Flask-SQLAlchemy no está instalado. Instala Flask-SQLAlchemy para usar la DB.')

        # Obtener la URL actual de la DB (priorizando la configuración de la app)
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')

        def db_url_invalida(url):
            if not url:
                return True
            try:
                p = urlparse(url)
            except Exception:
                return True
            # Si no hay usuario válido o se usa el placeholder 'user', considerarlo inválido
            username = p.username
            if username in (None, '', 'user'):
                return True
            return False

        # Si la URL parece inválida, avisar y usar fallback a sqlite local
        if db_url_invalida(db_url):
            print('DATABASE_URL ausente o inválida. Valor actual:', repr(db_url))
            print('Ejemplo de URL válida: postgresql://usuario:password@localhost:5432/transportes2025')
            print('Se aplicará un fallback a sqlite local: sqlite:///transportes2025.sqlite')
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transportes2025.sqlite'

        if models_db is not None:
            try:
                models_db.create_all()
            except Exception as e:
                # Mostrar mensaje claro y, si hay un problema con Postgres, intentar fallback a sqlite
                print('Error al conectar a la base de datos al crear tablas:', e)
                msg = str(e).lower()
                if 'role "user" does not exist'.lower() in msg or 'role "user" does not exist' in str(e):
                    print('Pista: el error indica que el rol/usuario "user" no existe en Postgres.')
                    print('Revisa tu variable DATABASE_URL (.env) y asegúrate de incluir usuario y contraseña correctos.')
                    print('Ejemplo: postgresql://miusuario:mipass@localhost:5432/transportes2025')
                print('Intentando crear tablas en sqlite local como respaldo...')
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transportes2025.sqlite'
                try:
                    models_db.create_all()
                    print('Tablas creadas en sqlite local.')
                except Exception as e2:
                    print('No se pudo crear tablas en sqlite:', e2)
                    print('Abortando inicialización de la base de datos.')
                    return

        # Si hay archivo Excel, poblar la DB (solo si los modelos están disponibles)
        EXCEL_FILE = os.environ.get('EXCEL_FILE', 'transportes2025.xlsx')
        if os.path.exists(EXCEL_FILE):
            if models_db is None or ModelVehiculo is None:
                print(f'Encontrado {EXCEL_FILE}, pero no se pueden poblar los datos porque falta Flask-SQLAlchemy.')
                print('Instala las dependencias: pip install Flask-SQLAlchemy psycopg2-binary python-dotenv')
                return

            print(f'Encontrado {EXCEL_FILE}, poblando la base de datos desde la hoja DETALLE...')
            
            # Leer específicamente la hoja DETALLE
            import pandas as pd
            df = pd.read_excel(EXCEL_FILE, sheet_name='DETALLE', header=0, dtype={'MATRICULA 2025': str})
            
            # Normalizar columnas
            from utils import normalizar_columna
            df.columns = [normalizar_columna(c) for c in df.columns]
            df = limpiar_nans(df)
            
            print(f'Columnas detectadas: {list(df.columns)}')
            print(f'Total de registros a importar: {len(df)}')
            
            # Evitar duplicados por ORD
            for _, row in df.iterrows():
                try:
                    ord_val = int(row.get('ORD')) if row.get('ORD') not in (None, '') else None
                except Exception:
                    ord_val = None
                if ord_val is None:
                    continue
                existing = ModelVehiculo.query.filter_by(ord=ord_val).first()
                if existing:
                    continue
                
                # Guardar todos los campos como string (excepto ORD que es Integer)
                v = ModelVehiculo(
                    ord=ord_val,
                    clase_tipo=str(row.get('CLASE / TIPO', '')),
                    marca=str(row.get('MARCA', '')),
                    modelo=str(row.get('MODELO', '')),
                    chasis=str(row.get('CHASIS', '')),
                    motor=str(row.get('MOTOR', '')),
                    ano=str(row.get('ANO', '')),
                    registro=str(row.get('REGISTRO', '')),
                    placas=str(row.get('PLACAS', '')),
                    color=str(row.get('COLOR', '')),
                    tonelaje=str(row.get('TONELAJE', '')),
                    cilindraje=str(row.get('CILINDRAJE', '')),
                    combustible=str(row.get('COMBUSTIBLE', '')),
                    num_pasajeros=str(row.get('# PASAJ', '')),
                    valor_esbye=str(row.get('VALOR ESBYE', '')),
                    valor_comercial=str(row.get('VALOR COMERCIAL', '')),
                    division=str(row.get('DIVISION', '')),
                    brigada=str(row.get('BRIGADA', '')),
                    unidad=str(row.get('UNIDAD', '')),
                    necesidad_operacional_ft=str(row.get('NECESIDAD OPERACIONAL FT', '')),
                    condicion=str(row.get('CONDICION', '')),
                    estado=str(row.get('ESTADO', '')),
                    codigo_esbye=str(row.get('CODIGO ESBYE', '')),
                    eod=str(row.get('EOD', '')),
                    digito=str(row.get('DIGITO', '')),
                    matricula_2025=str(row.get('MATRICULA 2025', '')),
                    custodio=str(row.get('CUSTODIO', '')),
                    observacion=str(row.get('OBSERVACION', ''))
                )
                models_db.session.add(v)
            models_db.session.commit()
            print('Población completada.')
        else:
            print(f'No se encontró {EXCEL_FILE}, consideración: la base de datos queda vacía.')


if __name__ == '__main__':
    app = create_app()
    init_db(app)
