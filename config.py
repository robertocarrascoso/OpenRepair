import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'openrepair_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'openrepair')
}

SECRET_KEY = os.getenv('SECRET_KEY', 'clave-de-desarrollo')

# Admin inicial: se crea solo en el primer arranque si no hay usuarios.
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@openrepair.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
ADMIN_NOMBRE = os.getenv('ADMIN_NOMBRE', 'Administrador')
