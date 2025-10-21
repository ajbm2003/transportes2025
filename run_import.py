
from app import create_app
from utils import guardar_excel_en_db

def main():
    app = create_app()
    with app.app_context():
        try:
            resultado = guardar_excel_en_db(force=True)
            print('Importación completada:', resultado)
        except Exception as e:
            print('Error durante la importación:', e)

if __name__ == '__main__':
    main()
