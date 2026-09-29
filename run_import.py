from app import create_app
from utils import guardar_excel_en_db
import os

def main():
    app = create_app()
    
    # Verificar qué base de datos se está usando
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    print(f'Configuración de base de datos: {db_uri}')
    
    # Validar que estamos usando PostgreSQL
    if not db_uri or 'postgresql' not in db_uri:
        print('\n❌ ERROR: No se está usando PostgreSQL')
        print(f'URI actual: {db_uri}')
        print('\nAsegúrate de que tu archivo .env tenga:')
        print('DATABASE_URL=postgresql://alejo:2003@localhost:5432/transportes2025')
        return
    
    print('✓ Usando PostgreSQL correctamente')
    
    with app.app_context():
        # Recrear las tablas
        print('\nRecreando tablas con la nueva estructura...')
        from models import db, Vehiculo
        
        try:
            # Eliminar todas las tablas existentes y recrearlas
            print('Eliminando tablas antiguas...')
            db.drop_all()
            print('Creando tablas nuevas...')
            db.create_all()
            print('✓ Tablas creadas correctamente en PostgreSQL.')
        except Exception as e:
            print(f'\n❌ Error al crear tablas en PostgreSQL: {e}')
            import traceback
            traceback.print_exc()
            print('\nPosibles soluciones:')
            print('1. Asegúrate de que PostgreSQL está corriendo: brew services start postgresql')
            print('2. Crea la base de datos: createdb transportes2025')
            print('3. Verifica usuario y contraseña en .env')
            return
        
        # Verificar que la conexión funciona
        try:
            count_before = Vehiculo.query.count()
            print(f'\nRegistros en la base de datos antes de importar: {count_before}')
        except Exception as e:
            print(f'\n❌ Error al verificar la base de datos: {e}')
            import traceback
            traceback.print_exc()
            return
        
        try:
            print('\nIniciando importación desde Excel...')
            resultado = guardar_excel_en_db(force=True)
            print('\n' + '='*50)
            print('Importación completada:', resultado)
            print('='*50)
            
            # Verificar cuántos registros se insertaron
            count_after = Vehiculo.query.count()
            print(f'\n📊 Registros en PostgreSQL después de importar: {count_after}')
            
            if count_after > 0:
                print('\n✅ ¡Importación exitosa en PostgreSQL!')
                # Mostrar algunos registros de ejemplo
                print('\nPrimeros 5 vehículos:')
                for v in Vehiculo.query.order_by(Vehiculo.ord).limit(5):
                    print(f'  ORD {v.ord}: {v.clase_tipo or "N/A"} - Placas: {v.placas or "N/A"} - División: {v.division or "N/A"}')
            else:
                print('\n⚠️ ADVERTENCIA: No se importaron registros a PostgreSQL')
                
        except Exception as e:
            print('\n❌ Error durante la importación:', e)
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()
