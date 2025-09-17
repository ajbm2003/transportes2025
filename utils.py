import pandas as pd
import unicodedata
import re

EXCEL_FILE = 'data/transportes2025.xlsx'
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
    df = pd.read_excel(EXCEL_FILE, dtype={'MATRICULA 2025': str})
    df.columns = [normalizar_columna(c) for c in df.columns]
    print("Columnas normalizadas:", list(df.columns))  # Depuración
    return df

def limpiar_nans(df):
    return df.fillna('')

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
