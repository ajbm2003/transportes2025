import pandas as pd
import unicodedata
import re
# pyrefly: ignore [missing-import]
from flask import current_app
import os
import time

try:
    from models import Vehiculo, db as models_db
except Exception:
    try:
        from models import Vehiculo
        models_db = None
    except Exception:
        Vehiculo = None
        models_db = None

# Caché simple en memoria para lecturas desde DB
_DB_CACHE = {'df': None, 'ts': 0}
_DEFAULT_TTL = 10  # segundos; configurable desde current_app.config['DB_CACHE_TTL']

EXCEL_FILE = os.environ.get('EXCEL_FILE', 'transportes2026.xlsx')
COLUMNAS = [
    'ORD', 'CLASE / TIPO', 'CHASIS', 'MOTOR', 'ANO', 'REGISTRO',
    'PLACAS', 'DIVISION', 'BRIGADA', 'UNIDAD',
    'NECESIDAD OPERACIONAL FT', 'CONDICION', 'ESTADO', 'OBSERVACION'
]

def normalizar_columna(col):
    # Quita tildes, pasa a mayúsculas, elimina espacios extra y caracteres especiales
    col = ''.join(
        c for c in unicodedata.normalize('NFD', col)
        if unicodedata.category(c) != 'Mn'
    )
    col = col.upper().strip()
    col = re.sub(r'\s+', ' ', col)  # Reemplaza múltiples espacios por uno
    col = col.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    col = col.replace('Ñ', 'N')
    col = col.replace('.', '')  # Opcional: elimina puntos si hay
    col = col.replace('/', ' / ')  # Asegura espacios alrededor de /
    col = col.replace('  ', ' ')
    return col

def cargar_datos():
    """Carga datos desde Excel. Si la app tiene una base de datos configurada y hay registros, devuelve los datos desde la DB."""
    # Si hay una app y modelos disponibles, intentar leer desde la DB (rápido)
    try:
        if Vehiculo is not None and current_app and current_app.config.get('SQLALCHEMY_DATABASE_URI'):
            # Usar caché para lecturas repetidas
            ttl = current_app.config.get('DB_CACHE_TTL', _DEFAULT_TTL)
            now = time.time()
            if _DB_CACHE['df'] is not None and (now - _DB_CACHE['ts'] < ttl):
                return _DB_CACHE['df']
            df = df_from_db()
            _DB_CACHE['df'] = df
            _DB_CACHE['ts'] = now
            return df
    except Exception:
        pass

    # Fallback: leer Excel - usar específicamente la hoja "DETALLE"
    df = pd.read_excel(EXCEL_FILE, sheet_name='DETALLE', header=0, dtype=str)
    df.columns = [normalizar_columna(c) for c in df.columns]
    df = limpiar_nans(df)
    # Asegurar orden por ORD cuando se lee desde Excel
    try:
        if 'ORD' in df.columns:
            df['ORD_SORT'] = pd.to_numeric(df['ORD'], errors='coerce')
            df = df.sort_values(by=['ORD_SORT']).drop(columns=['ORD_SORT'])
    except Exception as e:
        print(f'Advertencia al ordenar datos desde Excel: {e}')
    print("Columnas normalizadas:", list(df.columns))  # Depuración
    return df


def df_from_db():
    """Convierte los registros de la tabla Vehiculo a un DataFrame con las columnas normalizadas esperadas."""
    try:
        from models import Vehiculo, get_session
        session = get_session()
        vehiculos = session.query(Vehiculo).order_by(Vehiculo.ord.asc()).all()
        records = [v.to_dict() for v in vehiculos]
        session.close()
        if records:
            df = pd.DataFrame(records)
            df.columns = [normalizar_columna(c) for c in df.columns]
            if 'ORD' in df.columns:
                df['ORD'] = pd.to_numeric(df['ORD'], errors='coerce')
                df = df.sort_values(by=['ORD'])
            df = limpiar_nans(df)
            return df
    except Exception as e:
        print(f'Error leyendo desde DB: {e}')

    return pd.DataFrame(columns=COLUMNAS)


def get_divisiones_db():
    """Devuelve lista ordenada de divisiones usando el ORM de la BD."""
    try:
        from models import Vehiculo, get_session
        session = get_session()
        res = session.query(Vehiculo.division).filter(Vehiculo.division.isnot(None), Vehiculo.division != '').distinct().order_by(Vehiculo.division).all()
        divs = [r[0] for r in res if r[0]]
        session.close()
        if divs:
            return divs
    except Exception as e:
        print(f'Advertencia al obtener divisiones desde DB: {e}')
    return []


def get_brigadas_db(division):
    try:
        from models import Vehiculo, get_session
        if division:
            session = get_session()
            res = session.query(Vehiculo.brigada).filter(Vehiculo.division == division, Vehiculo.brigada.isnot(None), Vehiculo.brigada != '').distinct().order_by(Vehiculo.brigada).all()
            brigadas = [r[0] for r in res if r[0]]
            session.close()
            if brigadas:
                return brigadas
    except Exception as e:
        print(f'Advertencia al obtener brigadas desde DB: {e}')
    return []


def get_unidades_db(division, brigada):
    try:
        from models import Vehiculo, get_session
        if division and brigada:
            session = get_session()
            res = session.query(Vehiculo.unidad).filter(Vehiculo.division == division, Vehiculo.brigada == brigada, Vehiculo.unidad.isnot(None), Vehiculo.unidad != '').distinct().order_by(Vehiculo.unidad).all()
            unidades = [r[0] for r in res if r[0]]
            session.close()
            if unidades:
                return unidades
    except Exception as e:
        print(f'Advertencia al obtener unidades desde DB: {e}')
    return []


def limpiar_nans(df):
    df = df.fillna('')  # Rellenar valores NaN con cadenas vacías
    if 'PLACAS' in df.columns:
        # Normalizar: convertir a str, pasar a mayúsculas y eliminar cualquier carácter no alfanumérico
        # Ejemplo: " abc-123 " -> "ABC123"
        df['PLACAS'] = df['PLACAS'].astype(str).str.upper().str.replace(r'[^A-Z0-9]', '', regex=True)
    return df

def obtener_opciones(df, division=None, brigada=None):
    # Asegúrate de que las columnas existen
    if 'DIVISION' not in df.columns:
        raise Exception(f"No se encontró la columna 'DIVISION'. Columnas disponibles: {list(df.columns)}")
    divisiones = sorted(df['DIVISION'].dropna().unique())
    if division:
        brigadas = sorted(df[df['DIVISION'] == division]['BRIGADA'].dropna().unique()) if 'BRIGADA' in df.columns else []
    else:
        brigadas = []
    if division and brigada:
        unidades = sorted(df[(df['DIVISION'] == division) & (df['BRIGADA'] == brigada)]['UNIDAD'].dropna().unique()) if 'UNIDAD' in df.columns else []
    else:
        unidades = []
    return divisiones, brigadas, unidades

def filtrar_vehiculos(df, division=None, brigada=None, unidad=None):
    if division and 'DIVISION' in df.columns:
        df = df[df['DIVISION'] == division]
    if brigada and 'BRIGADA' in df.columns:
        df = df[df['BRIGADA'] == brigada]
    if unidad and 'UNIDAD' in df.columns:
        df = df[df['UNIDAD'] == unidad]
    return df

# Nueva función para invalidar caché desde la app cuando se hagan cambios (commit/guardar)
def invalidate_db_cache():
    """Invalidar la caché de datos leídos desde la base de datos."""
    global _DB_CACHE
    _DB_CACHE['df'] = None
    _DB_CACHE['ts'] = 0


def guardar_excel_en_db(excel_path=None, force=False):
    """
    Lee el Excel y lo inserta en la base de datos usando el modelo Vehiculo.
    Si force=True, borra todos los registros antes de importar.
    """
    from models import Vehiculo, get_session
    session = get_session()
    excel_file = excel_path or os.environ.get('EXCEL_FILE', 'transportes2026.xlsx')
    
    print(f'Leyendo archivo: {excel_file}')
    
    if not os.path.exists(excel_file):
        msg = f"❌ ERROR: No se encontró el archivo '{excel_file}' en la carpeta del proyecto."
        print(f"\n{msg}")
        print(f"💡 Solución: Asegúrate de colocar tu archivo Excel con el nombre '{excel_file}' dentro de la carpeta del proyecto:\n   {os.getcwd()}")
        return msg
    
    xls = pd.ExcelFile(excel_file)
    print(f'Hojas disponibles en el Excel: {xls.sheet_names}')
    
    sheet_to_read = 'DETALLE' if 'DETALLE' in xls.sheet_names else xls.sheet_names[0]
    print(f'Usando hoja: {sheet_to_read}')
    
    try:
        df_raw = pd.read_excel(excel_file, sheet_name=sheet_to_read, header=None, dtype=str)
        header_row = 0
        for idx, row in df_raw.head(15).iterrows():
            row_str_upper = [str(cell).upper().strip() for cell in row.values if pd.notna(cell)]
            if any('ORD' in cell for cell in row_str_upper) or any('CLASE' in cell for cell in row_str_upper) or any('PLACA' in cell for cell in row_str_upper):
                header_row = idx
                break
    except Exception as e:
        print(f'Aviso al detectar encabezado: {e}')
        header_row = 0
        
    df = pd.read_excel(excel_file, sheet_name=sheet_to_read, header=header_row, dtype=str)
    
    df.columns = [normalizar_columna(str(c)) for c in df.columns]
    print(f'Columnas detectadas ({len(df.columns)}): {list(df.columns)}')
    
    if 'ORD' not in df.columns:
        possible_ord_cols = [c for c in df.columns if 'ORD' in c or 'ITEM' in c or 'N' in c]
        if possible_ord_cols:
            df.rename(columns={possible_ord_cols[0]: 'ORD'}, inplace=True)
        else:
            df['ORD'] = [str(i + 1) for i in range(len(df))]
    
    df = df.fillna('')
    print(f'Total de filas en Excel a procesar: {len(df)}')
    
    if force:
        deleted = session.query(Vehiculo).delete()
        session.commit()
        print(f'Registros eliminados de la base de datos previamente: {deleted}')
    
    count = 0
    errores = 0
    
    for idx, row in df.iterrows():
        raw_ord = str(row.get('ORD', '')).strip()
        if not raw_ord:
            continue
        try:
            ord_val = int(float(raw_ord))
        except Exception:
            ord_val = idx + 1
            
        try:
            v = Vehiculo(
                ord=ord_val,
                clase_tipo=str(row.get('CLASE / TIPO', row.get('CLASE TIPO', row.get('CLASE', '')))).strip(),
                chasis=str(row.get('CHASIS', '')).strip(),
                motor=str(row.get('MOTOR', '')).strip(),
                ano=str(row.get('ANO', row.get('ANO', ''))).strip(),
                registro=str(row.get('REGISTRO', '')).strip(),
                placas=str(row.get('PLACAS', row.get('PLACA', ''))).strip(),
                division=str(row.get('DIVISION', '')).strip(),
                brigada=str(row.get('BRIGADA', '')).strip(),
                unidad=str(row.get('UNIDAD', '')).strip(),
                necesidad_operacional_ft=str(row.get('NECESIDAD OPERACIONAL FT', row.get('NECESIDAD OPERACIONAL', ''))).strip(),
                condicion=str(row.get('CONDICION', '')).strip().upper(),
                estado=str(row.get('ESTADO', '')).strip().upper(),
                observacion=str(row.get('OBSERVACION', '')).strip()
            )
            session.add(v)
            count += 1
            
            if count % 100 == 0:
                session.commit()
        except Exception as e:
            print(f'Aviso en fila {idx+1} (ORD={ord_val}): {e}')
            session.rollback()
            errores += 1
    
    try:
        session.commit()
        invalidate_db_cache()
    except Exception as e:
        print(f'Error en commit final: {e}')
        session.rollback()
    finally:
        session.close()
    
    print(f'\n✅ Importación completada: {count} registros cargados, {errores} errores.')
    return f"{count} registros importados correctamente, {errores} errores"

def query_vehiculos(division=None, brigada=None, unidad=None, placa=None, limit=None, offset=None):
    """
    Consulta directa desde la BD usando get_session().
    """
    try:
        from models import Vehiculo, get_session
        session = get_session()
        q = session.query(Vehiculo)
        if division:
            q = q.filter(Vehiculo.division == division)
        if brigada:
            q = q.filter(Vehiculo.brigada == brigada)
        if unidad:
            q = q.filter(Vehiculo.unidad == unidad)
        if placa:
            placa_norm = re.sub(r'[^A-Z0-9]', '', placa.strip().upper())
            q = q.filter(Vehiculo.placas.ilike(f"%{placa_norm}%"))
        
        q = q.order_by(Vehiculo.ord.asc())
        if offset is not None:
            q = q.offset(int(offset))
        if limit is not None:
            q = q.limit(int(limit))
        
        records = [v.to_dict() for v in q.all()]
        session.close()
        if records:
            df = pd.DataFrame(records)
            return limpiar_nans(df)
    except Exception as e:
        print(f'Advertencia: error en query_vehiculos: {e}')

    return pd.DataFrame(columns=COLUMNAS)


def count_vehiculos(division=None, brigada=None, unidad=None, placa=None):
    """
    Devuelve el total de registros que cumplen los filtros usando get_session().
    """
    try:
        from models import Vehiculo, get_session
        session = get_session()
        q = session.query(Vehiculo)
        if division:
            q = q.filter(Vehiculo.division == division)
        if brigada:
            q = q.filter(Vehiculo.brigada == brigada)
        if unidad:
            q = q.filter(Vehiculo.unidad == unidad)
        if placa:
            placa_norm = re.sub(r'[^A-Z0-9]', '', placa.strip().upper())
            q = q.filter(Vehiculo.placas.ilike(f"%{placa_norm}%"))
        count = q.count()
        session.close()
        return count
    except Exception as e:
        print(f'Advertencia al contar vehiculos en DB: {e}')

    return 0