import pandas as pd
import unicodedata
import re
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

EXCEL_FILE = 'transportes2025.xlsx'
COLUMNAS = [
    'ORD', 'MARCA', 'CLASE / TIPO', 'ANO', 'PLACAS', 'COLOR',
    'CONDICION', 'ESTADO', 'OBSERVACION', 'MATRICULA 2025', 'DIVISION', 'BRIGADA', 'UNIDAD'
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

    # Fallback: leer Excel (solo si no hay BD)
    df = pd.read_excel(EXCEL_FILE, dtype={'MATRICULA 2025': str})
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
    """Convierte los registros de la tabla Vehiculo a un DataFrame con las columnas normalizadas esperadas.
    Implementación rápida usando SQL directo si models_db está disponible.
    """
    # Si disponemos del engine de SQLAlchemy, usar read_sql_query para rapidez
    if models_db is not None:
        try:
            engine = models_db.engine
            # Consulta que selecciona y aliasa columnas para coincidir con COLUMNAS
            sql = """
                SELECT
                    ord AS ORD,
                    marca AS MARCA,
                    clase_tipo AS "CLASE / TIPO",
                    ano AS ANO,
                    placas AS PLACAS,
                    color AS COLOR,
                    condicion AS CONDICION,
                    estado AS ESTADO,
                    observacion AS OBSERVACION,
                    matricula_2025 AS "MATRICULA 2025",
                    division AS DIVISION,
                    brigada AS BRIGADA,
                    unidad AS UNIDAD
                FROM vehiculos
                ORDER BY ord
            """
            df = pd.read_sql_query(sql, engine)
            # Normalizar columnas y valores mínimamente
            df.columns = [normalizar_columna(c) for c in df.columns]
            df = limpiar_nans(df)
            # Asegurar que ORD es numérico y ordenado (por si acaso)
            try:
                if 'ORD' in df.columns:
                    df['ORD'] = pd.to_numeric(df['ORD'], errors='coerce')
                    df = df.sort_values(by=['ORD'])
            except Exception as e:
                print(f'Advertencia al ordenar datos desde DB (post-process): {e}')
            return df
        except Exception as e:
            print(f'Error leyendo desde DB con read_sql_query: {e}')
            # caemos al método por objetos ORM más lento

    # Fallback: leer mediante ORM (compatible pero más lento)
    records = []
    try:
        for v in Vehiculo.query.order_by(Vehiculo.ord.asc()).all():
            records.append(v.to_dict())
    except Exception as e:
        print(f'Error leyendo desde DB (ORM): {e}')
    if not records:
        return pd.DataFrame(columns=COLUMNAS)
    df = pd.DataFrame(records)
    df.columns = [normalizar_columna(c) for c in df.columns]
    try:
        if 'ORD' in df.columns:
            df['ORD'] = pd.to_numeric(df['ORD'], errors='coerce')
            df = df.sort_values(by=['ORD'])
    except Exception as e:
        print(f'Advertencia al ordenar datos desde DB (ORM post-process): {e}')
    df = limpiar_nans(df)
    return df


# Funciones rápidas para obtener divisiones / brigadas / unidades desde la BD sin leer todo el Excel
def get_divisiones_db():
    """Devuelve lista ordenada de divisiones usando la BD si está disponible, sino usa cargar_datos()."""
    if models_db is not None:
        try:
            sql = "SELECT DISTINCT division FROM vehiculos WHERE division IS NOT NULL AND division <> '' ORDER BY division"
            df = pd.read_sql_query(sql, models_db.engine)
            return sorted(df['division'].dropna().unique().tolist())
        except Exception as e:
            print(f'Advertencia al obtener divisiones desde DB: {e}')
    # Fallback
    df = cargar_datos()
    return sorted(df['DIVISION'].dropna().unique().tolist()) if 'DIVISION' in df.columns else []


def get_brigadas_db(division):
    if models_db is not None:
        try:
            sql = "SELECT DISTINCT brigada FROM vehiculos WHERE division = %s AND brigada IS NOT NULL AND brigada <> '' ORDER BY brigada"
            # usar read_sql_query con params
            df = pd.read_sql_query(sql, models_db.engine, params=(division,))
            return sorted(df['brigada'].dropna().unique().tolist())
        except Exception as e:
            print(f'Advertencia al obtener brigadas desde DB: {e}')
    df = cargar_datos()
    if 'DIVISION' in df.columns and 'BRIGADA' in df.columns:
        return sorted(df[df['DIVISION'] == division]['BRIGADA'].dropna().unique().tolist())
    return []


def get_unidades_db(division, brigada):
    if models_db is not None:
        try:
            sql = "SELECT DISTINCT unidad FROM vehiculos WHERE division = %s AND brigada = %s AND unidad IS NOT NULL AND unidad <> '' ORDER BY unidad"
            df = pd.read_sql_query(sql, models_db.engine, params=(division, brigada))
            return sorted(df['unidad'].dropna().unique().tolist())
        except Exception as e:
            print(f'Advertencia al obtener unidades desde DB: {e}')
    df = cargar_datos()
    if 'DIVISION' in df.columns and 'BRIGADA' in df.columns and 'UNIDAD' in df.columns:
        return sorted(df[(df['DIVISION'] == division) & (df['BRIGADA'] == brigada)]['UNIDAD'].dropna().unique().tolist())
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


# --- FUNCION PARA IMPORTAR EXCEL A LA DB ---
def guardar_excel_en_db(force=False):
    """
    Lee el Excel y lo inserta en la base de datos usando el modelo Vehiculo.
    Si force=True, borra todos los registros antes de importar.
    """
    from models import Vehiculo, db
    excel_file = os.environ.get('EXCEL_FILE', EXCEL_FILE)
    df = pd.read_excel(excel_file, dtype={'MATRICULA 2025': str})
    df = df.fillna('')
    if force:
        Vehiculo.query.delete()
        db.session.commit()
    count = 0
    for _, row in df.iterrows():
        v = Vehiculo(
            ord=int(row.get('ORD', 0) or 0),
            marca=row.get('MARCA', ''),
            clase_tipo=row.get('CLASE / TIPO', ''),
            ano=int(row.get('ANO', 0) or 0),
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
        db.session.add(v)
        count += 1
    db.session.commit()
    return f"{count} registros importados"

def query_vehiculos(division=None, brigada=None, unidad=None, placa=None, limit=None, offset=None):
    """
    Consulta rápida desde la BD con soporte de offset (paginación).
    El filtro por placa se hace en SQL si posible, normalizando la búsqueda.
    """
    if models_db is not None:
        try:
            # Detectar motor (Postgres o SQLite)
            engine_name = str(models_db.engine.url.get_backend_name()).lower()
            sql = """
                SELECT
                    ord AS ORD,
                    marca AS MARCA,
                    clase_tipo AS "CLASE / TIPO",
                    ano AS ANO,
                    placas AS PLACAS,
                    color AS COLOR,
                    condicion AS CONDICION,
                    estado AS ESTADO,
                    observacion AS OBSERVACION,
                    matricula_2025 AS "MATRICULA 2025",
                    division AS DIVISION,
                    brigada AS BRIGADA,
                    unidad AS UNIDAD
                FROM vehiculos
                WHERE 1=1
            """
            params = {}
            if division:
                sql += " AND division = :division"
                params['division'] = division
            if brigada:
                sql += " AND brigada = :brigada"
                params['brigada'] = brigada
            if unidad:
                sql += " AND unidad = :unidad"
                params['unidad'] = unidad
            # Filtro por placa en SQL si posible
            if placa:
                placa_norm = re.sub(r'[^A-Z0-9]', '', placa.strip().upper())
                if engine_name == "postgresql":
                    # Usar ILIKE y regexp_replace para normalizar en SQL
                    sql += " AND regexp_replace(upper(placas), '[^A-Z0-9]', '', 'g') ILIKE :placa"
                    params['placa'] = f"%{placa_norm}%"
                elif engine_name == "sqlite":
                    # Usar LIKE y upper() para SQLite
                    sql += " AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(upper(placas),' ',''),'-',''),'.',''),'/',''),',',''),';',''),':',''),'_',''),'#',''),'Ñ','N') LIKE :placa"
                    params['placa'] = f"%{placa_norm}%"
                else:
                    # Otros motores: filtrar en pandas después
                    pass
            sql += " ORDER BY ord"
            if limit is not None:
                sql += " LIMIT :limit"
                params['limit'] = int(limit)
            if offset is not None:
                sql += " OFFSET :offset"
                params['offset'] = int(offset)

            df = pd.read_sql_query(sql, models_db.engine, params=params)
            df.columns = [normalizar_columna(c) for c in df.columns]
            df = limpiar_nans(df)

            # Si el motor no soporta filtro SQL por placa, filtrar en pandas
            if placa and engine_name not in ("postgresql", "sqlite") and 'PLACAS' in df.columns:
                placa_norm = re.sub(r'[^A-Z0-9]', '', placa.strip().upper())
                df = df[df['PLACAS'].astype(str).str.contains(placa_norm, na=False)]

            return df
        except Exception as e:
            print(f'Advertencia: error en query_vehiculos (SQL rápido): {e}')
            # caer al fallback

    # Fallback: usar cargar_datos y filtrar en pandas (más lento)
    df = cargar_datos()
    if division:
        df = df[df['DIVISION'] == division] if 'DIVISION' in df.columns else df
    if brigada:
        df = df[df['BRIGADA'] == brigada] if 'BRIGADA' in df.columns else df
    if unidad:
        df = df[df['UNIDAD'] == unidad] if 'UNIDAD' in df.columns else df
    if placa and 'PLACAS' in df.columns:
        placa_norm = re.sub(r'[^A-Z0-9]', '', placa.strip().upper())
        df = df[df['PLACAS'].astype(str).str.contains(placa_norm, na=False)]
    if offset is not None and limit is not None:
        df = df.iloc[offset: offset + limit]
    elif limit is not None:
        df = df.head(limit)
    try:
        if 'ORD' in df.columns:
            df['ORD_SORT'] = pd.to_numeric(df['ORD'], errors='coerce')
            df = df.sort_values(by=['ORD_SORT']).drop(columns=['ORD_SORT'])
    except Exception:
        pass
    return df


def count_vehiculos(division=None, brigada=None, unidad=None, placa=None):
    """
    Devuelve el total de registros que cumplen filtros (rápido usando COUNT en DB si es posible).
    """
    if models_db is not None:
        try:
            sql = "SELECT COUNT(*) AS cnt FROM vehiculos WHERE 1=1"
            params = {}
            if division:
                sql += " AND division = :division"
                params['division'] = division
            if brigada:
                sql += " AND brigada = :brigada"
                params['brigada'] = brigada
            if unidad:
                sql += " AND unidad = :unidad"
                params['unidad'] = unidad
            # Si se incluye placa, realizar conteo conservador (sin normalizar en SQL)
            # Para placas, mejor fallback: leer matching parcial en pandas si es necesario
            if placa:
                # usar fallback lento: obtener df y contar
                df = query_vehiculos(division=division, brigada=brigada, unidad=unidad, placa=placa)
                return int(len(df))
            df = pd.read_sql_query(sql, models_db.engine, params=params)
            return int(df['cnt'].iloc[0]) if not df.empty else 0
        except Exception as e:
            print(f'Advertencia al contar vehiculos en DB: {e}')
    # Fallback: contar desde cargar_datos()
    df = cargar_datos()
    if division:
        df = df[df['DIVISION'] == division] if 'DIVISION' in df.columns else df
    if brigada:
        df = df[df['BRIGADA'] == brigada] if 'BRIGADA' in df.columns else df
    if unidad:
        df = df[df['UNIDAD'] == unidad] if 'UNIDAD' in df.columns else df
    if placa and 'PLACAS' in df.columns:
        placa_norm = re.sub(r'[^A-Z0-9]', '', placa.strip().upper())
        df = df[df['PLACAS'].astype(str).str.contains(placa_norm, na=False)]
    return int(len(df))