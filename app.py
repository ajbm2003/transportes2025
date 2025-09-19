from flask import Flask, render_template, request, redirect, url_for, send_file, session
import os
import threading  # Importar threading para usar el semáforo
from utils import cargar_datos, limpiar_nans, obtener_opciones, filtrar_vehiculos, COLUMNAS

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET_KEY', 'mi_clave0705')  # Usa variable de entorno

EXCEL_FILE = 'transportes2025.xlsx'
LOGIN_USER = os.getenv("LOGIN_USER", "javier76")
LOGIN_PASS = os.getenv("LOGIN_PASS", "mecanico76")

# Crear un semáforo global
excel_lock = threading.Lock()

@app.route('/')
def index():
    df = cargar_datos()
    df = limpiar_nans(df)
    division_filtro = request.args.get('division')
    brigada_filtro = request.args.get('brigada')
    unidad_filtro = request.args.get('unidad')
    placa_filtro = request.args.get('placa')  # Obtener el filtro de placa

    divisiones, brigadas, unidades = obtener_opciones(df, division_filtro, brigada_filtro)
    df_display = filtrar_vehiculos(df[COLUMNAS], division_filtro, brigada_filtro, unidad_filtro)

    if placa_filtro:  # Filtrar por placa si se proporciona
        placa_filtro = placa_filtro.strip().upper()  # Normalizar el valor ingresado
        df_display = df_display[df_display['PLACAS'].str.upper().str.contains(placa_filtro, na=False)]

    return render_template(
        'index.html',
        vehicles=df_display.to_dict(orient='records'),
        divisiones=divisiones,
        brigadas=brigadas,
        unidades=unidades,
        selected_division=division_filtro or '',
        selected_brigada=brigada_filtro or '',
        selected_unidad=unidad_filtro or ''
    )

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
    return send_file(EXCEL_FILE, as_attachment=True, download_name='transportes_actualizado.xlsx')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/editar_vehiculo', methods=['POST'])
def editar_vehiculo():
    ord_id = request.form.get('ord')  # Identificador único del registro
    nueva_condicion = request.form.get('condicion')
    nuevo_estado = request.form.get('estado')  # Puede ser vacío
    nueva_observacion = request.form.get('observacion', '')
    
    if not ord_id:  # Validar que se haya proporcionado el identificador ORD
        return redirect(url_for('index'))
    
    # Usar el semáforo para garantizar acceso exclusivo al archivo Excel
    print("Intentando adquirir el semáforo para editar el archivo Excel...")
    with excel_lock:
        print("Semáforo adquirido. Editando el archivo Excel...")
        df = cargar_datos()
        
        # Filtrar el registro específico por su número de ORD
        registro_especifico = df['ORD'] == int(ord_id)
        if registro_especifico.any():  # Verificar que el registro exista
            if nueva_condicion:
                df.loc[registro_especifico, 'CONDICION'] = nueva_condicion
            # Permitir que el estado sea vacío
            df.loc[registro_especifico, 'ESTADO'] = nuevo_estado
            df.loc[registro_especifico, 'OBSERVACION'] = nueva_observacion
            
            # Guardar los cambios en el archivo Excel
            df.to_excel(EXCEL_FILE, index=False)
            print(f"Edición completada para el registro con ORD {ord_id}. Liberando el semáforo...")
        else:
            print(f"No se encontró ningún registro con el ORD {ord_id}.")
    
    print("Semáforo liberado.")
    return redirect(url_for('index'))


if __name__ == '__main__':
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: {EXCEL_FILE} no encontrado en el directorio.")
    else:
        port = int(os.environ.get('PORT', 8080))  # Usa el puerto de Render
        app.run(host='0.0.0.0', port=port)
        print(f"Error: {EXCEL_FILE} no encontrado en el directorio.")
