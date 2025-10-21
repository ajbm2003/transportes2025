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

            print(f'Encontrado {EXCEL_FILE}, poblando la base de datos...')
            df = cargar_datos()
            df = limpiar_nans(df)
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
                v = ModelVehiculo(
                    ord=ord_val,
                    marca=row.get('MARCA', ''),
                    clase_tipo=row.get('CLASE / TIPO', ''),
                    ano=row.get('ANO') if row.get('ANO') not in (None, '') else None,
                    placas=row.get('PLACAS', ''),
                    color=row.get('COLOR', ''),
                    condicion=row.get('CONDICION', ''),
                    estado=row.get('ESTADO', ''),
                    observacion=row.get('OBSERVACION', ''),
                    matricula_2025=row.get('MATRICULA 2025', ''),
                    division=row.get('DIVISION', ''),
                    brigada=row.get('BRIGADA', ''),
                    unidad=row.get('UNIDAD', '')
                )
                models_db.session.add(v)
            models_db.session.commit()
            print('Población completada.')
        else:
            print(f'No se encontró {EXCEL_FILE}, consideración: la base de datos queda vacía.')


if __name__ == '__main__':
    app = create_app()
    init_db(app)
