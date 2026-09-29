from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify
import os
import threading
import pandas as pd
import re
import io

# Import seguro de load_dotenv (puede faltar python-dotenv)
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        print('Aviso: python-dotenv no está instalado. Las variables de entorno no se cargarán desde .env. Instala python-dotenv si quieres cargar .env automáticamente.')

# Añadir invalidate_db_cache y guardar_excel_en_db al importar utils
from utils import cargar_datos, limpiar_nans, obtener_opciones, filtrar_vehiculos, COLUMNAS, get_divisiones_db, get_brigadas_db, get_unidades_db, invalidate_db_cache, query_vehiculos, count_vehiculos, guardar_excel_en_db


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.secret_key = os.environ.get('APP_SECRET_KEY', 'mi_clave0705')

    # Configurar SQLAlchemy
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Fallback: usar sqlite local para pruebas si no hay DATABASE_URL
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transportes.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Importar modelos/DB solo en tiempo de ejecución para evitar errores si falta la dependencia
    try:
        from models import db as models_db, Vehiculo as ModelVehiculo
    except Exception:
        models_db = None
        ModelVehiculo = None
        print('Aviso: Flask-SQLAlchemy no está disponible. Instala Flask-SQLAlchemy para usar Postgres.')

    if models_db:
        try:
            models_db.init_app(app)
        except Exception as e:
            print(f'Aviso al inicializar db: {e}')

    EXCEL_FILE = os.environ.get('EXCEL_FILE', 'transportes2026.xlsx')
    LOGIN_USER = os.getenv("LOGIN_USER", "javier76")
    LOGIN_PASS = os.getenv("LOGIN_PASS", "mecanico76")

    # Crear un semáforo global para operaciones de escritura
    excel_lock = threading.Lock()

    # Variables globales para divisiones, brigadas y unidades
    divisiones_global = []
    brigadas_global = {}
    unidades_global = {}

    def inicializar_filtros():
        nonlocal divisiones_global, brigadas_global, unidades_global
        try:
            # Intentar inicializar con consultas rápidas a la BD (no leer todo Excel)
            try:
                divisiones_global = get_divisiones_db()
                for division in divisiones_global:
                    brigadas = get_brigadas_db(division)
                    brigadas_global[division] = brigadas
                    for brigada in brigadas:
                        unidades = get_unidades_db(division, brigada)
                        unidades_global[(division, brigada)] = unidades
                return
            except Exception as e:
                print(f'Advertencia: no se pudo inicializar filtros usando consultas rápidas: {e}')
            # Fallback: leer DataFrame completo si las consultas rápidas fallan
            df = cargar_datos()
            if df is not None and not df.empty and 'DIVISION' in df.columns:
                divisiones_global, _, _ = obtener_opciones(df)
                for division in divisiones_global:
                    brigadas = obtener_opciones(df, division=division)[1]
                    brigadas_global[division] = brigadas
                    for brigada in brigadas:
                        unidades = obtener_opciones(df, division=division, brigada=brigada)[2]
                        unidades_global[(division, brigada)] = unidades
        except Exception as e:
            print(f"Aviso al inicializar filtros: {e}")
            divisiones_global = []
            brigadas_global = {}
            unidades_global = {}

    # Inicializar base de datos y filtros al arrancar la app de forma totalmente segura
    try:
        with app.app_context():
            if models_db:
                try:
                    models_db.create_all()
                    if ModelVehiculo:
                        try:
                            if ModelVehiculo.query.count() == 0 and os.path.exists(EXCEL_FILE):
                                print(f"Base de datos vacía. Poblando automáticamente desde {EXCEL_FILE}...")
                                guardar_excel_en_db(excel_path=EXCEL_FILE, force=False)
                        except Exception as e:
                            print(f"Aviso al verificar contenido de la tabla vehiculos: {e}")
                except Exception as e:
                    print(f"Aviso al verificar/crear tablas en la BD: {e}")
            inicializar_filtros()
    except Exception as e:
        print(f"Aviso general en app_context al inicio: {e}")

    @app.route('/init-db')
    def route_init_db():
        try:
            if models_db:
                models_db.create_all()
            res = guardar_excel_en_db(excel_path=EXCEL_FILE, force=False)
            inicializar_filtros()
            return f"✅ Base de datos inicializada e importada con éxito: {res}"
        except Exception as e:
            return f"❌ Error al inicializar la base de datos: {e}", 200


    @app.route('/')
    def index():
        try:
            division_filtro = request.args.get('division', '')
            brigada_filtro = request.args.get('brigada', '')
            unidad_filtro = request.args.get('unidad', '')
            placa_filtro = request.args.get('placa', '')

            brigadas = brigadas_global.get(division_filtro, []) if brigadas_global else []
            unidades = unidades_global.get((division_filtro, brigada_filtro), []) if unidades_global else []

            return render_template(
                'index.html',
                vehicles=[],
                divisiones=divisiones_global or [],
                brigadas=brigadas,
                unidades=unidades,
                selected_division=division_filtro,
                selected_brigada=brigada_filtro,
                selected_unidad=unidad_filtro
            )
        except Exception as e:
            print(f"Error al cargar la página principal: {e}")
            return render_template(
                'index.html',
                vehicles=[],
                divisiones=[],
                brigadas=[],
                unidades=[],
                selected_division='',
                selected_brigada='',
                selected_unidad=''
            )

    # API para paginación / búsqueda (devuelve JSON)
    @app.route('/api/vehiculos')
    def api_vehiculos():
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            division = request.args.get('division') or None
            brigada = request.args.get('brigada') or None
            unidad = request.args.get('unidad') or None
            placa = request.args.get('placa') or None

            offset = (page - 1) * per_page
            df_page = query_vehiculos(division=division, brigada=brigada, unidad=unidad, placa=placa, limit=per_page, offset=offset)
            total = count_vehiculos(division=division, brigada=brigada, unidad=unidad, placa=placa)

            records = df_page.to_dict(orient='records') if (df_page is not None and not df_page.empty) else []
            return jsonify({'total': total or 0, 'page': page, 'per_page': per_page, 'vehicles': records})
        except Exception as e:
            print(f'Error en API /api/vehiculos: {e}')
            return jsonify({'total': 0, 'page': 1, 'per_page': 50, 'vehicles': [], 'error': str(e)}), 200


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            if username == LOGIN_USER and password == LOGIN_PASS:
                session['logged_in'] = True
                return redirect(url_for('download_excel'))
            else:
                return render_template('login.html', error="Usuario o contraseña incorrectos")
        return render_template('login.html')


    @app.route('/download')
    def download_excel():
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        # Usar query_vehiculos para obtener todos los registros desde la BD (rápido)
        df = query_vehiculos()
        # Asegurar orden por ORD al exportar
        try:
            if 'ORD' in df.columns:
                df['ORD_SORT'] = pd.to_numeric(df['ORD'], errors='coerce')
                df = df.sort_values(by=['ORD_SORT']).drop(columns=['ORD_SORT'])
        except Exception as e:
            print(f'Advertencia al ordenar antes de exportar: {e}')

        # Escribir el Excel en memoria y enviarlo (evita I/O en disco)
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            output.seek(0)
            return send_file(output, as_attachment=True, download_name='transportes_actualizado.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e:
            print(f'Error al generar Excel en memoria: {e}')
            return "Error generando el archivo", 500


    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        return redirect(url_for('index'))


    @app.route('/editar_vehiculo', methods=['POST'])
    def editar_vehiculo():
        ord_id = request.form.get('ord')
        nueva_condicion = (request.form.get('condicion') or '').strip().upper()
        nuevo_estado = (request.form.get('estado') or '').strip().upper()
        nueva_observacion = (request.form.get('observacion') or '').strip()

        if not ord_id:
            return jsonify({'error': 'ORD es requerido'}), 400

        # Validaciones de campos editables (permitiendo vacío si no tiene valor)
        if nueva_condicion not in ['', 'OPERABLE', 'NO OPERABLE']:
            return jsonify({'error': 'Condición no válida. Valores permitidos: OPERABLE, NO OPERABLE o vacío.'}), 400

        if nuevo_estado not in ['', 'SERVIBLE', 'INSERVIBLE']:
            return jsonify({'error': 'Estado no válido. Valores permitidos: SERVIBLE, INSERVIBLE o vacío.'}), 400

        palabras = [p for p in nueva_observacion.split() if p]
        if len(palabras) > 250:
            return jsonify({'error': f'La observación no puede superar las 250 palabras (actualmente tiene {len(palabras)} palabras).'}), 400

        with excel_lock:
            try:
                # Intentar actualizar en la DB
                try:
                    veh = ModelVehiculo.query.filter_by(ord=int(ord_id)).first() if ModelVehiculo is not None else None
                except Exception:
                    veh = None
                if veh:
                    veh.condicion = nueva_condicion
                    veh.estado = nuevo_estado
                    veh.observacion = nueva_observacion
                    
                    if models_db is not None:
                        models_db.session.commit()
                        try:
                            invalidate_db_cache()
                        except Exception:
                            pass
                else:
                    # Si no existe en la DB, actualizar el Excel (compatibilidad)
                    df = cargar_datos()
                    registro_especifico = df['ORD'] == int(ord_id)
                    if registro_especifico.any():
                        df.loc[registro_especifico, 'CONDICION'] = nueva_condicion
                        df.loc[registro_especifico, 'ESTADO'] = nuevo_estado
                        df.loc[registro_especifico, 'OBSERVACION'] = nueva_observacion
                        df.to_excel(EXCEL_FILE, index=False)
                        try:
                            invalidate_db_cache()
                        except Exception:
                            pass
            except Exception as e:
                print(f"Error al guardar los cambios: {e}")
                return jsonify({'error': 'Error interno del servidor'}), 500

        return jsonify({'success': True, 'message': 'Cambios guardados correctamente'})

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
