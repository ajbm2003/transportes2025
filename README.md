# transportes2025

Aplicación Flask para gestionar vehículos. Esta versión usa PostgreSQL a través de SQLAlchemy y está preparada para deployment.

Requisitos
- Python 3.10+

Instalación local

1. Crear un virtualenv y activar:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Copiar `.env.example` a `.env` y editar variables (DATABASE_URL, APP_SECRET_KEY, etc.).

4. Inicializar la base de datos (pobla desde el archivo Excel si existe):

```bash
python init_db.py
```

5. Ejecutar en desarrollo:

```bash
python app.py
```

Deploy

- El `Procfile` está configurado para usar Gunicorn: `web: gunicorn "app:create_app()" --workers 3 --bind 0.0.0.0:$PORT`.
- Configura la variable de entorno `DATABASE_URL` con tu conexión PostgreSQL en la plataforma (Heroku, Render, etc.).

Variables de entorno importantes
- DATABASE_URL: URL de PostgreSQL (ej: postgresql://user:pass@host:5432/dbname)
- APP_SECRET_KEY: clave secreta de Flask
- LOGIN_USER / LOGIN_PASS: credenciales para descargar el Excel
- EXCEL_FILE: nombre del Excel local para inicialización si se desea

Notas
- Si no se proporciona `DATABASE_URL`, se usa un SQLite local (`transportes.db`) como fallback para pruebas.
- `init_db.py` popula la base de datos desde `transportes2025.xlsx` si existe.

